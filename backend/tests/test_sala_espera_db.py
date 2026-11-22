"""GET /sala-espera contra una base real (S11-10, US-04).

Se omite sin DATABASE_URL y APP_ENCRYPTION_KEY. La base tiene episodios de otras pruebas,
así que los de esta prueba se crean en un día viejo y al azar: son los únicos de ese día
(turnos A-1, A-2, ...) y los únicos con más de un millón de minutos de espera, lo que
permite reconocerlos sin que la respuesta traiga episodio_id.

La letra del turno depende del día, así que las pruebas comparan solo el número y
revisan que todos los turnos propios compartan la misma letra.
"""
import os
import random
import re
from datetime import datetime, timedelta

import psycopg
import pytest

from test_decision_db import _episodio, client

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)

URL = "/api/v1/sala-espera"
MUY_ANTIGUO = 1_000_000  # minutos; los episodios de otras pruebas esperan mucho menos

# etiqueta: (nivel sugerido por la IA, nivel final de enfermería, estado). El orden de la
# lista es el de llegada, así que el número de turno esperado es 1, 2, ... en este orden.
# La sala solo muestra el nivel FINAL: el sugerido no se publica.
EPISODIOS = [
    ("t1", 2, 2, "en_espera"),        # 1
    ("t2", 3, 1, "en_espera"),        # 2: la enfermera subió la urgencia -> ESI 1
    ("t3", 2, 2, "en_atencion"),      # 3
    ("t4", 1, 1, "en_espera"),        # 4
    ("t5", 2, 2, "cerrado"),          # 5: no aparece, pero ocupa su número
    ("t6", 2, 2, "en_espera"),        # 6
    ("t7", 1, None, "en_espera"),     # 7: la IA sugirió ESI 1 pero nadie confirmó -> sin nivel
]

# Escrito a mano: ESI 1 primero y, a igual nivel, el que llegó antes. Sin nivel, al final.
ORDEN_ESPERADO = [2, 4, 1, 3, 6, 7]


def _admin():
    return psycopg.connect(os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"])


@pytest.fixture(scope="module")
def sala_de_prueba():
    # Un día al azar entre 1990 y 2010, a las 15:00 UTC (mediodía en Chile).
    dia = datetime(1990, 1, 1, 15, 0) + timedelta(days=random.randrange(7300))
    ids = []
    for k, (_, sugerido, final, estado) in enumerate(EPISODIOS):
        ep = _episodio(sugerido=sugerido)
        ids.append(ep)
        with _admin() as conn:
            conn.execute(
                "UPDATE episodio_triage SET fecha_hora_ingreso = %s, estado = %s "
                "WHERE episodio_id = %s",
                (dia + timedelta(minutes=10 * k), estado, ep),
            )
            if final is not None:
                conn.execute(
                    """
                    INSERT INTO decision_clinica
                        (decision_id, episodio_id, nivel_esi_final, coincide_con_ia,
                         justificacion, fecha_hora_decision)
                    VALUES (gen_random_uuid(), %s, %s, false,
                            'Ajuste clínico de prueba.', now() AT TIME ZONE 'UTC')
                    """,
                    (ep, final),
                )
    yield ids
    # Se cierran para no ensuciar la sala en la próxima corrida contra la misma base.
    with _admin() as conn:
        conn.execute(
            "UPDATE episodio_triage SET estado = 'cerrado' WHERE episodio_id = ANY(%s)", (ids,)
        )


def _sala() -> list[dict]:
    r = client.get(URL)  # sin token, a propósito
    assert r.status_code == 200, r.text
    return r.json()


def _propios(sala: list[dict]) -> list[dict]:
    return [f for f in sala if f["minutos_espera"] > MUY_ANTIGUO]


def _numero(turno: str) -> int:
    return int(turno.split("-")[1])


def _por_numero(sala: list[dict]) -> dict[int, dict]:
    return {_numero(f["turno"]): f for f in _propios(sala)}


def test_orden_turnos_y_cerrado_fuera(sala_de_prueba):
    propios = _propios(_sala())
    assert [_numero(f["turno"]) for f in propios] == ORDEN_ESPERADO
    assert len({f["turno"].split("-")[0] for f in propios}) == 1  # misma letra: mismo día


def test_letra_valida_aunque_el_dia_sea_anterior_al_2000(sala_de_prueba):
    # Los episodios de la prueba caen entre 1990 y 2010: la letra tiene que ser A..Z igual.
    assert all(re.fullmatch(r"[A-Z]-[0-9]+", f["turno"]) for f in _propios(_sala()))


def test_turnos_no_se_repiten(sala_de_prueba):
    turnos = [f["turno"] for f in _sala()]
    assert len(turnos) == len(set(turnos))


def test_nivel_vigente_y_estado(sala_de_prueba):
    fila = _por_numero(_sala())
    assert fila[2]["nivel_esi"] == 1  # nivel final, no el sugerido (3)
    assert fila[3]["estado"] == "en_atencion"
    assert fila[3]["posicion"] is None
    # Todos llevan años esperando: ya cumplieron el objetivo de su categoría.
    assert all(fila[n]["tiempo_estimado_min"] == 0 for n in (1, 2, 3, 4, 6))


def test_sugerencia_de_la_ia_sin_confirmar_no_se_publica(sala_de_prueba):
    fila = _por_numero(_sala())
    assert fila[7]["nivel_esi"] is None  # la IA sugirió 1, pero enfermería no confirmó
    assert fila[7]["tiempo_estimado_min"] is None


def test_posiciones_consecutivas_en_el_orden_de_la_lista(sala_de_prueba):
    sala = _sala()
    posiciones = [f["posicion"] for f in sala if f["estado"] == "en_espera"]
    assert posiciones == list(range(1, len(posiciones) + 1))
    assert all(f["posicion"] is None for f in sala if f["estado"] == "en_atencion")
    # Los ESI 1 de la prueba son los que más esperan: van primeros en la fila.
    fila = _por_numero(sala)
    assert (fila[2]["posicion"], fila[4]["posicion"]) == (1, 2)


def test_toda_la_lista_respeta_la_prioridad(sala_de_prueba):
    sala = _sala()
    claves = [(f["nivel_esi"] is None, f["nivel_esi"] or 0, -f["minutos_espera"]) for f in sala]
    assert claves == sorted(claves)
    assert len(sala) <= 100


def test_sin_datos_personales_ni_ids(sala_de_prueba):
    r = client.get(URL)
    assert "Ana Soto" not in r.text  # nombre que usan los pacientes de prueba
    for ep in sala_de_prueba:
        assert ep not in r.text
    for f in r.json():
        assert set(f) == {
            "turno", "nivel_esi", "estado", "posicion", "minutos_espera", "tiempo_estimado_min",
        }


def test_rls_contexto_sala_espera_no_ve_pacientes(sala_de_prueba):
    """Con app.rol = 'sala_espera' la base no entrega pacientes ni usuarios (migración 0013)."""
    from app.db import ROL_SALA_ESPERA, set_rls_context

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        set_rls_context(conn, ROL_SALA_ESPERA)
        assert conn.execute("SELECT count(*) FROM paciente").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM usuario_staff").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM signos_vitales").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM clasificacion_ia").fetchone()[0] == 0
        # Pero sí ve los episodios que necesita para armar la fila.
        assert conn.execute(
            "SELECT count(*) FROM episodio_triage WHERE episodio_id = ANY(%s)",
            (sala_de_prueba,),
        ).fetchone()[0] == len(EPISODIOS)
