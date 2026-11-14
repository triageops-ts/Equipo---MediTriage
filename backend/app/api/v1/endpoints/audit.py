"""POST /audit-logs/client-events: registra en la bitácora un fallo de guardado."""
import uuid

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb

from app.core.audit_chain import HASH_GENESIS, calcular_hash
from app.db import get_conn
from app.schemas.audit import EventoAuditoriaResponse, EventoFalloGuardadoInput

router = APIRouter(prefix="/audit-logs")

EVENTO_FALLO_GUARDADO = "decision_guardado_fallido"
ENTIDAD = "episodio_triage"

# Serializa las escrituras para que la cadena no se bifurque si llegan dos a la vez.
_LOCK_CADENA = "SELECT pg_advisory_xact_lock(hashtextextended('registro_auditoria', 0))"
_EXISTE_EPISODIO = "SELECT 1 FROM episodio_triage WHERE episodio_id = %(id)s"
_EXISTE_USUARIO = "SELECT 1 FROM usuario_staff WHERE usuario_id = %(id)s"
_ULTIMO_HASH = """
    SELECT hash_actual FROM registro_auditoria
    ORDER BY fecha_hora_evento DESC, registro_id DESC
    LIMIT 1
"""
_AHORA_UTC = "SELECT (now() AT TIME ZONE 'UTC')"
_INSERT = """
    INSERT INTO registro_auditoria
        (registro_id, evento_tipo, entidad_afectada, entidad_id, usuario_id,
         detalle_json, hash_anterior, hash_actual, fecha_hora_evento)
    VALUES
        (%(registro_id)s, %(evento_tipo)s, %(entidad)s, %(entidad_id)s, %(usuario_id)s,
         %(detalle)s, %(hash_anterior)s, %(hash_actual)s, %(fecha)s)
"""


@router.post(
    "/client-events",
    response_model=EventoAuditoriaResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Auditoría"],
    summary="Registra que el navegador no pudo guardar la decisión de la enfermera",
)
def registrar_fallo_guardado(
    data: EventoFalloGuardadoInput, conn: psycopg.Connection = Depends(get_conn)
):
    registro_id = uuid.uuid4()
    # Solo contadores y categorías: sin contenido clínico ni datos personales.
    detalle = {
        "tipo_error": data.tipo_error,
        "intentos": data.intentos,
        "recuperado": data.recuperado,
        "primer_fallo_cliente": data.primer_fallo_cliente.isoformat(),
    }

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(_EXISTE_EPISODIO, {"id": data.episodio_id})
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No existe un episodio de triage con id {data.episodio_id}.",
                )
            if data.usuario_id is not None:
                cur.execute(_EXISTE_USUARIO, {"id": data.usuario_id})
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No existe un usuario con id {data.usuario_id}.",
                    )

            cur.execute(_LOCK_CADENA)
            cur.execute(_ULTIMO_HASH)
            fila = cur.fetchone()
            hash_anterior = fila[0] if fila and fila[0] else HASH_GENESIS

            cur.execute(_AHORA_UTC)
            fecha = cur.fetchone()[0]  # hora de la base de datos, no la del cliente

            hash_actual = calcular_hash(
                hash_anterior=hash_anterior,
                evento_tipo=EVENTO_FALLO_GUARDADO,
                entidad_afectada=ENTIDAD,
                entidad_id=data.episodio_id,
                usuario_id=data.usuario_id,
                detalle=detalle,
                fecha_hora_evento=fecha,
            )
            cur.execute(
                _INSERT,
                {
                    "registro_id": registro_id,
                    "evento_tipo": EVENTO_FALLO_GUARDADO,
                    "entidad": ENTIDAD,
                    "entidad_id": data.episodio_id,
                    "usuario_id": data.usuario_id,
                    "detalle": Jsonb(detalle),
                    "hash_anterior": hash_anterior,
                    "hash_actual": hash_actual,
                    "fecha": fecha,
                },
            )

    return EventoAuditoriaResponse(
        registro_id=registro_id,
        evento_tipo=EVENTO_FALLO_GUARDADO,
        hash_actual=hash_actual,
        fecha_hora_evento=fecha,
    )