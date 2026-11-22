"""GET /sala-espera: pantalla pública de la sala de espera (S11-10, US-04).

No pide token: la ve cualquiera en la sala. Por eso:
- la conexión usa el contexto RLS `sala_espera`, que solo puede leer episodio_triage,
  clasificacion_ia y decision_clinica (migración 0013): ni paciente, ni contactos, ni RUT;
- la consulta no lee nombre, RUT, paciente_id ni motivo de consulta, y la respuesta no
  lleva episodio_id: solo un turno anonimizado (letra del día + correlativo de llegada,
  ej. "A-12"; la letra cambia cada día para que no se repitan turnos de días distintos);
- tiene límite de peticiones por IP (429 al superarlo).

Orden: el mismo de la cola clínica (S10-3). ESI 1 arriba; a igual nivel, el que lleva más
tiempo esperando; los episodios sin nivel van al final. episodio_id desempata para que el
orden sea estable aunque cambien varios turnos a la vez.
"""
import psycopg
from fastapi import APIRouter, Depends, Response

from app.core.rate_limit import limite_sala_espera
from app.db import get_conn_sala_espera
from app.schemas.cola import ESTADOS_ACTIVOS
from app.schemas.sala_espera import (
    MAX_FILAS_SALA,
    ZONA_HORARIA_TURNOS,
    SalaEsperaEntry,
    formatear_turno,
    tiempo_estimado,
)

router = APIRouter()

# Nivel vigente: el final si la enfermera ya decidió; si no, el último sugerido por la IA.
# El turno se numera con TODOS los episodios del día (también los cerrados), así el número
# de un paciente no cambia cuando otros terminan su atención.
_SALA_ESPERA = """
    WITH activos AS (
        SELECT
            e.episodio_id,
            e.estado,
            e.fecha_hora_ingreso,
            COALESCE(dc.nivel_esi_final, cia.nivel_esi_sugerido) AS nivel_esi,
            ((e.fecha_hora_ingreso AT TIME ZONE 'UTC') AT TIME ZONE %(zona)s)::date AS dia
        FROM episodio_triage e
        LEFT JOIN LATERAL (
            SELECT nivel_esi_sugerido
            FROM clasificacion_ia
            WHERE episodio_id = e.episodio_id
            ORDER BY tiempo_respuesta DESC NULLS LAST
            LIMIT 1
        ) cia ON TRUE
        LEFT JOIN decision_clinica dc ON dc.episodio_id = e.episodio_id
        WHERE e.estado = ANY(%(estados)s)
          AND e.fecha_hora_ingreso IS NOT NULL
    ),
    turnos AS (
        SELECT
            d.episodio_id,
            -- Letra del día (A..Z, rota cada 26 días): dos días distintos no comparten turno.
            -- En Postgres % puede dar negativo (días antes del 2000): se suma 26 y se vuelve
            -- a tomar el resto para que siempre quede entre 0 y 25.
            chr(65 + ((((d.dia - DATE '2000-01-01') %% 26) + 26) %% 26)) AS letra,
            row_number() OVER (
                PARTITION BY d.dia ORDER BY d.fecha_hora_ingreso, d.episodio_id
            ) AS numero
        FROM (
            SELECT
                episodio_id,
                fecha_hora_ingreso,
                ((fecha_hora_ingreso AT TIME ZONE 'UTC') AT TIME ZONE %(zona)s)::date AS dia
            FROM episodio_triage
            WHERE fecha_hora_ingreso IS NOT NULL
        ) d
        WHERE d.dia IN (SELECT dia FROM activos)
    ),
    ordenados AS (
        SELECT
            t.letra,
            t.numero,
            a.nivel_esi,
            a.estado,
            a.fecha_hora_ingreso,
            a.episodio_id,
            GREATEST(
                0,
                floor(extract(epoch FROM ((now() AT TIME ZONE 'UTC') - a.fecha_hora_ingreso)) / 60)
            )::int AS minutos_espera,
            row_number() OVER (
                PARTITION BY a.estado
                ORDER BY a.nivel_esi ASC NULLS LAST, a.fecha_hora_ingreso ASC, a.episodio_id ASC
            ) AS lugar
        FROM activos a
        JOIN turnos t ON t.episodio_id = a.episodio_id
    )
    SELECT
        letra,
        numero,
        nivel_esi,
        estado,
        CASE WHEN estado = 'en_espera' THEN lugar END AS posicion,
        minutos_espera
    FROM ordenados
    ORDER BY nivel_esi ASC NULLS LAST, fecha_hora_ingreso ASC, episodio_id ASC
    LIMIT %(limit)s
"""


@router.get(
    "/sala-espera",
    response_model=list[SalaEsperaEntry],
    tags=["Sala de espera"],
    summary="Vista pública de la sala de espera",
    description=(
        "Pantalla pública (sin token). Turnos anonimizados de los episodios en espera y en "
        "atención, ordenados por prioridad ESI, con su posición y el tiempo estimado por "
        "categoría. Nunca incluye RUT, nombre, patient_id ni episodio_id."
    ),
    dependencies=[Depends(limite_sala_espera)],
)
def sala_espera(
    response: Response,
    conn: psycopg.Connection = Depends(get_conn_sala_espera),
):
    with conn.cursor() as cur:
        cur.execute(
            _SALA_ESPERA,
            {
                "zona": ZONA_HORARIA_TURNOS,
                "estados": list(ESTADOS_ACTIVOS),
                "limit": MAX_FILAS_SALA,
            },
        )
        filas = cur.fetchall()

    # El monitor consulta cada pocos segundos: que ningún proxy ni navegador guarde la lista.
    response.headers["Cache-Control"] = "no-store"
    return [construir_fila(*fila) for fila in filas]


def construir_fila(letra, numero, nivel_esi, estado, posicion, minutos_espera) -> SalaEsperaEntry:
    return SalaEsperaEntry(
        turno=formatear_turno(letra, numero),
        nivel_esi=nivel_esi,
        estado=estado,
        posicion=posicion,
        minutos_espera=minutos_espera,
        tiempo_estimado_min=tiempo_estimado(nivel_esi, estado, minutos_espera),
    )
