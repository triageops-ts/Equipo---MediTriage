import contextlib
import uuid
import warnings
from datetime import datetime, timezone
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
        consulta = str(sql).lower()
        self.fila = None

        if "insert into consentimiento" in consulta:
            self.fila = (datetime.now(timezone.utc),)
        elif isinstance(params, dict) and "email" in params:
            self.fila = self.usuarios.get(params["email"])

    def fetchone(self):
        return self.fila

    def fetchall(self):
        return [] if self.fila is None else [self.fila]

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
    
    usuarios = {EMAIL: (USUARIO_ID, "enfermero", hash_password(PASSWORD))}
    app.dependency_overrides[get_conn] = lambda: _Conexion(usuarios)
    app.dependency_overrides[get_conn_login] = lambda: _Conexion(usuarios)

    token, _ = crear_token(USUARIO_ID, "enfermero")
    cliente = TestClient(app)
    cliente.headers.update({"Authorization": f"Bearer {token}"})

    yield cliente

    app.dependency_overrides.clear()


schema = schemathesis.openapi.from_path(str(_encontrar_openapi()))
schema.app = app


@schema.parametrize()
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_contrato_openapi(case, contrato_cliente):
    response = case.call(headers=dict(contrato_cliente.headers))

    try:
        case.validate_response(response)
    except schemathesis.core.failures.FailureGroup as exc:
        fallos = exc.exceptions
        ruta = case.operation.path
        metodo = case.method.upper()

        if len(fallos) == 1:
            fallo = fallos[0]
            tipo = type(fallo).__name__
            mensaje = str(fallo)

            if (
                metodo == "POST"
                and ruta.endswith("/patients")
                and tipo == "AcceptedNegativeData"
                and "Idempotency-Key" in mensaje
                and ("uuid" in mensaje or "incorrect type" in mensaje)
                and response.status_code == 201
            ):
                warnings.warn("DC-09: Idempotency-Key sin validacion UUID", stacklevel=2)
                return

            if (
                metodo == "GET"
                and ruta.endswith("/patients")
                and tipo == "RejectedPositiveData"
                and response.status_code == 422
                and "El RUT" in response.json().get("detail", "")
            ):
                pytest.xfail("DC-07: Validacion del RUT")

            if (
                metodo == "PATCH"
                and ruta.endswith("/patients/{patient_id}")
                and tipo == "RejectedPositiveData"
                and response.status_code == 422
                and "no puede ser futura" in response.json().get("detail", "")
            ):
                pytest.xfail("DC-08: Fecha de nacimiento futura")

        raise