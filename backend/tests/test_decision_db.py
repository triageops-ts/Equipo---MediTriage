"""Pruebas de POST /triage/{id}/decision contra una base real.

Se omiten si no hay DATABASE_URL y APP_ENCRYPTION_KEY. Como todavía no existe un
endpoint que genere la sugerencia de la IA, cada prueba la inserta a mano en
`clasificacion_ia`.
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


def _episodio(sugerido: int | None = 3) -> str:
    """Crea paciente + episodio por la API; inserta la sugerencia de la IA si se pide."""
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

    if sugerido is not None:
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


def _fila_decision(episodio_id: str):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(
            "SELECT nivel_esi_final, coincide_con_ia, justificacion "
            "FROM decision_clinica WHERE episodio_id = %s",
            (episodio_id,),
        ).fetchall()


def test_confirmar_sin_justificacion():
    ep = _episodio(sugerido=3)
    r = _decidir(ep, nivel_esi_final=3)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["coincide_con_ia"] is True and b["modificado_manualmente"] is False
    assert b["nivel_esi_sugerido"] == 3 and b["nivel_esi_final"] == 3
    assert _fila_decision(ep) == [(3, True, None)]


def test_modificar_con_justificacion_marca_modificado_manualmente():
    ep = _episodio(sugerido=3)
    r = _decidir(ep, nivel_esi_final=2, justificacion="Dificultad respiratoria no captada en triage.")
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["coincide_con_ia"] is False and b["modificado_manualmente"] is True
    assert b["nivel_esi_sugerido"] == 3 and b["nivel_esi_final"] == 2
    assert _fila_decision(ep) == [(2, False, "Dificultad respiratoria no captada en triage.")]


def test_modificar_sin_justificacion_422_y_no_guarda():
    ep = _episodio(sugerido=3)
    r = _decidir(ep, nivel_esi_final=2)
    assert r.status_code == 422
    assert "explicar el motivo" in r.json()["detail"]
    assert _fila_decision(ep) == []


def test_modificar_con_justificacion_muy_corta_422():
    ep = _episodio(sugerido=3)
    assert _decidir(ep, nivel_esi_final=1, justificacion="grave").status_code == 422
    assert _fila_decision(ep) == []


def test_episodio_inexistente_404():
    assert _decidir(str(uuid.uuid4()), nivel_esi_final=3).status_code == 404


def test_sin_sugerencia_de_ia_409():
    ep = _episodio(sugerido=None)
    r = _decidir(ep, nivel_esi_final=3)
    assert r.status_code == 409
    assert "sugerencia de la IA" in r.json()["detail"]


def test_segunda_decision_409_y_no_reemplaza():
    ep = _episodio(sugerido=3)
    assert _decidir(ep, nivel_esi_final=3).status_code == 201
    r = _decidir(ep, nivel_esi_final=2, justificacion="Cambio de criterio clínico posterior.")
    assert r.status_code == 409
    assert _fila_decision(ep) == [(3, True, None)]


def test_nivel_fuera_de_rango_422():
    ep = _episodio(sugerido=3)
    r = _decidir(ep, nivel_esi_final=6)
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"].endswith("nivel_esi_final")


def test_id_de_episodio_invalido_422():
    r = client.post("/api/v1/triage/no-es-un-uuid/decision", json={"nivel_esi_final": 3})
    assert r.status_code == 422