"""S07-8: la sugerencia original de la IA y la decisión del profesional se conservan las dos.

Archivo independiente (no modifica test_decision_db.py). Se omite si no hay DATABASE_URL
y APP_ENCRYPTION_KEY. Las dos últimas pruebas requieren la migración 0003 aplicada en la
base que se está probando.
"""
import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)

client = TestClient(app)

SIGNOS = {
    "presion_sistolica": 120,
    "presion_diastolica": 80,
    "frecuencia_cardiaca": 80,
    "frecuencia_respiratoria": 16,
    "temperatura": 36.5,
    "saturacion_oxigeno": 98,
    "escala_dolor": 3,
    "nivel_conciencia": "alerta",
}


def _rut_unico() -> str:
    from app.core.rut import calcular_dv, formatear_rut

    cuerpo = str(10_000_000 + uuid.uuid4().int % 80_000_000)
    return formatear_rut(f"{cuerpo}-{calcular_dv(cuerpo)}")


def _usuario_id():
    """Un usuario real de usuario_staff, o None si la tabla está vacía."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        fila = conn.execute("SELECT usuario_id FROM usuario_staff LIMIT 1").fetchone()
    return str(fila[0]) if fila else None


def _episodio(sugerido: int = 3) -> str:
    """Crea paciente + episodio por la API e inserta a mano la sugerencia de la IA."""
    p = client.post(
        "/api/v1/patients", json={"rut": _rut_unico(), "name": "Ana Soto", "has_consent": True}
    )
    assert p.status_code == 201
    body = {"patient_id": p.json()["patient_id"], "signos_vitales": SIGNOS}
    if (uid := _usuario_id()) is not None:
        body["usuario_id"] = uid
    f = client.post("/api/v1/triage/formulario", json=body)
    assert f.status_code == 201, f.text
    episodio_id = f.json()["episodio_id"]

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            """
            INSERT INTO clasificacion_ia
                (clasificacion_id, episodio_id, token_correlacion_efimero,
                 nivel_esi_sugerido, tiempo_solicitud, tiempo_respuesta,
                 modelo_usado, hash_datos_enviados_ia, justificacion_ia)
            VALUES (%s, %s, %s, %s, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC',
                    'test', 'hash-de-prueba', 'sugerencia de prueba')
            """,
            (uuid.uuid4(), episodio_id, uuid.uuid4(), sugerido),
        )
    return episodio_id


def _decidir(episodio_id: str, **datos):
    if (uid := _usuario_id()) is not None:
        datos.setdefault("usuario_id", uid)
    return client.post(f"/api/v1/triage/{episodio_id}/decision", json=datos)


def _fila_ia(episodio_id: str):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(
            "SELECT nivel_esi_sugerido, justificacion_ia "
            "FROM clasificacion_ia WHERE episodio_id = %s",
            (episodio_id,),
        ).fetchall()


def _fila_decision(episodio_id: str):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(
            "SELECT nivel_esi_final, coincide_con_ia, justificacion "
            "FROM decision_clinica WHERE episodio_id = %s",
            (episodio_id,),
        ).fetchall()


def test_modificar_conserva_la_sugerencia_original_de_la_ia():
    ep = _episodio(sugerido=3)
    justificacion = "Dificultad respiratoria no captada en triage."
    assert _decidir(ep, nivel_esi_final=2, justificacion=justificacion).status_code == 201
    # La sugerencia de la IA sigue intacta y la decisión del profesional está aparte.
    assert _fila_ia(ep) == [(3, "sugerencia de prueba")]
    assert _fila_decision(ep) == [(2, False, justificacion)]


def test_confirmar_conserva_la_sugerencia_original_de_la_ia():
    ep = _episodio(sugerido=3)
    assert _decidir(ep, nivel_esi_final=3).status_code == 201
    assert _fila_ia(ep) == [(3, "sugerencia de prueba")]
    assert _fila_decision(ep) == [(3, True, None)]


# --- Requieren la migración 0003 (la base rechaza modificar o borrar estas filas) ---------


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE clasificacion_ia SET nivel_esi_sugerido = 1 WHERE episodio_id = %s",
        "DELETE FROM clasificacion_ia WHERE episodio_id = %s",
    ],
)
def test_la_base_no_deja_modificar_ni_borrar_la_sugerencia_de_la_ia(sql):
    ep = _episodio(sugerido=3)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="solo inserción"):
            conn.execute(sql, (ep,))
    assert _fila_ia(ep) == [(3, "sugerencia de prueba")]


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE decision_clinica SET nivel_esi_final = 1 WHERE episodio_id = %s",
        "DELETE FROM decision_clinica WHERE episodio_id = %s",
    ],
)
def test_la_base_no_deja_modificar_ni_borrar_la_decision_del_profesional(sql):
    ep = _episodio(sugerido=3)
    assert _decidir(ep, nivel_esi_final=3).status_code == 201
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="solo inserción"):
            conn.execute(sql, (ep,))
    assert _fila_decision(ep) == [(3, True, None)]
