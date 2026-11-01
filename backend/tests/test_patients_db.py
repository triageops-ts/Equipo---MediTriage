"""Pruebas de POST /patients contra una base real.

Se omiten si no hay DATABASE_URL (levantar con `docker compose up db` y aplicar
init.sql). Requiere además APP_ENCRYPTION_KEY.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)

client = TestClient(app)


def _rut_unico() -> str:
    from app.core.rut import calcular_dv, formatear_rut

    cuerpo = str(10_000_000 + uuid.uuid4().int % 80_000_000)
    return formatear_rut(f"{cuerpo}-{calcular_dv(cuerpo)}")


def test_crea_paciente_y_consentimiento():
    rut = _rut_unico()
    r = client.post("/api/v1/patients", json={"rut": rut, "name": "Ana Soto", "has_consent": True})
    assert r.status_code == 201
    body = r.json()
    assert body["rut"] == rut
    assert body["consent_version"] == "1.0"
    assert body["consent_accepted_at"]


def test_rut_duplicado_409():
    rut = _rut_unico()
    datos = {"rut": rut, "name": "Ana Soto", "has_consent": True}
    assert client.post("/api/v1/patients", json=datos).status_code == 201
    r = client.post("/api/v1/patients", json=datos)
    assert r.status_code == 409
    assert rut in r.json()["detail"]


def test_rut_invalido_422_con_mensaje():
    r = client.post(
        "/api/v1/patients", json={"rut": "11.111.111-2", "name": "Ana Soto", "has_consent": True}
    )
    assert r.status_code == 422
    err = r.json()["errors"][0]
    assert err["field"] == "rut" and "dígito verificador" in err["message"]
