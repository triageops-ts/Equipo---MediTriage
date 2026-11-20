"""GET /triage/cola: control de acceso sin base de datos (S10-3).

El rol se revisa antes de abrir la conexión, así que estas pruebas no necesitan
DATABASE_URL. Las de orden y contenido están en test_cola_db.py.
"""
import uuid

from fastapi.testclient import TestClient

from app.core.security import crear_token
from app.main import app

client = TestClient(app)
URL = "/api/v1/triage/cola"


def _cabecera(rol: str) -> dict:
    return {"Authorization": f"Bearer {crear_token(uuid.uuid4(), rol)[0]}"}


def test_sin_token_401():
    assert client.get(URL).status_code == 401


def test_auditor_403():
    r = client.get(URL, headers=_cabecera("auditor"))
    assert r.status_code == 403
