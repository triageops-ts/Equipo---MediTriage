import contextlib
import uuid
from pathlib import Path

import pytest
import schemathesis
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings

from app.core.security import crear_token, hash_password
from app.db import get_conn, get_conn_login
from app.main import app

PASSWORD = "Demo-2026!"
EMAIL = "enfermero@meditriage.test"
USUARIO_ID = uuid.uuid4()


class _Cursor:
    def __init__(self, usuarios):
        self.usuarios = usuarios
        self.fila = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.fila = self.usuarios.get((params or {}).get("email"))

    def fetchone(self):
        return self.fila


class _Conexion:
    def __init__(self, usuarios):
        self.usuarios = usuarios

    def cursor(self):
        return _Cursor(self.usuarios)

    def transaction(self):
        return contextlib.nullcontext()


def _encontrar_openapi() -> Path:
    actual = Path(__file__).resolve()
    for padre in [actual.parent, *actual.parents]:
        candidato = padre / "api" / "openapi.yaml"
        if candidato.exists():
            return candidato
    raise FileNotFoundError("No se encontró api/openapi.yaml en el repositorio")


@pytest.fixture
def contrato_cliente(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "clave-de-pruebas-0123456789-0123456789-abcdef")
    monkeypatch.setenv("APP_RUT_HASH_KEY", "clave-hash-rut-de-pruebas-0123456789")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "clave-de-cifrado-de-pruebas")

    usuarios = {EMAIL: (USUARIO_ID, "enfermero", hash_password(PASSWORD))}
    app.dependency_overrides[get_conn] = lambda: _Conexion(usuarios)
    app.dependency_overrides[get_conn_login] = lambda: _Conexion(usuarios)

    token, _ = crear_token(USUARIO_ID, "enfermero")
    cliente = TestClient(app)
    cliente.headers.update({"Authorization": f"Bearer {token}"})

    yield cliente

    app.dependency_overrides.clear()


schema = schemathesis.from_path(str(_encontrar_openapi()))


@schema.parametrize()
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_contrato_openapi(case, contrato_cliente):
    response = case.call(session=contrato_cliente)
    assert response is not None
    if response.status_code != 401:
        case.validate_response(response)
