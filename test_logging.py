"""Pruebas de logging estructurado y PII enmascarada (Factor 11). No necesitan base de datos:
la conexión se reemplaza por una falsa con dependency_overrides."""
import io
import json
import logging
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.logging_config import MASCARA, JsonFormatter, mascarar_texto, ruta_sin_parametros
from app.core.rut import calcular_dv
from app.db import get_conn
from app.main import app

NOMBRE = "Ana Soto Pérez"
EMAIL = "ana.soto@example.com"
TELEFONO = "+56 9 8765 4321"
DIRECCION = "Av. Siempre Viva 742"
RUT_BODY = "12345678"
RUT = f"12.345.678-{calcular_dv(RUT_BODY)}"


# --- Unitarias del formatter --------------------------------------------------------


def _linea(msg="evento", args=(), exc_info=None, **extra) -> dict:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, exc_info)
    for k, v in extra.items():
        setattr(record, k, v)
    salida = JsonFormatter().format(record)
    assert "\n" not in salida  # una línea por evento
    return json.loads(salida)


def test_linea_es_json_con_campos_base():
    d = _linea("hola")
    assert {"timestamp", "level", "logger", "message", "request_id"} <= set(d)
    assert d["level"] == "INFO" and d["message"] == "hola"


@pytest.mark.parametrize(
    "texto",
    [
        f"rut {RUT}",
        f"rut {RUT_BODY}-{calcular_dv(RUT_BODY)}",
        f"rut {RUT_BODY}{calcular_dv(RUT_BODY)}",
        f"correo {EMAIL}",
        f"fono {TELEFONO}",
        "fono 987654321",
    ],
)
def test_mascara_rut_correo_y_telefono_en_mensaje(texto):
    d = _linea("dato: %s", (texto,))
    assert MASCARA in d["message"]
    for crudo in (RUT, RUT_BODY, EMAIL, "8765 4321", "987654321"):
        assert crudo not in d["message"]


def test_no_destruye_uuid_ni_numeros_normales():
    pid = str(uuid.uuid4())
    assert mascarar_texto(f"patient {pid} status 201 duracion 12.5") == (
        f"patient {pid} status 201 duracion 12.5"
    )
    assert _linea("x", patient_id=pid)["patient_id"] == pid


def test_ruta_sin_valores_de_parametros():
    assert ruta_sin_parametros("/api/v1/patients/12345678-5/consents", {"rut": "12345678-5"}) == (
        "/api/v1/patients/{rut}/consents"
    )
    assert ruta_sin_parametros("/api/v1/health", {}) == "/api/v1/health"
    # un valor corto no debe reemplazar el "v1" de la ruta
    assert ruta_sin_parametros("/api/v1/x/1", {"n": "1"}) == "/api/v1/x/{n}"


def test_campos_extra_con_nombre_de_pii_se_reemplazan_completos():
    d = _linea("x", rut="cualquier cosa", nombre=NOMBRE, email=EMAIL, direccion=DIRECCION)
    assert d["rut"] == d["nombre"] == d["email"] == d["direccion"] == MASCARA


def test_dicts_anidados_y_listas_se_sanean():
    d = _linea("x", payload={"name": NOMBRE, "ok": 1, "notas": [f"llamar a {EMAIL}"]})
    assert d["payload"]["name"] == MASCARA
    assert d["payload"]["ok"] == 1
    assert EMAIL not in json.dumps(d)


def test_traceback_se_enmascara():
    try:
        raise ValueError(f"fallo con rut {RUT} y correo {EMAIL}")
    except ValueError:
        import sys

        d = _linea("boom", exc_info=sys.exc_info())
    assert "ValueError" in d["exception"]
    assert RUT not in d["exception"] and EMAIL not in d["exception"]


# --- Integración: POST /patients ---------------------------------------------------


class _Cursor:
    def __init__(self, existe: bool):
        self.existe = existe
        self.ultima = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.ultima = sql

    def fetchone(self):
        if "SELECT 1 FROM paciente" in self.ultima:
            return (1,) if self.existe else None
        return (datetime(2026, 11, 1, tzinfo=timezone.utc),)  # RETURNING fecha_hora


class _Conn:
    def __init__(self, existe=False):
        self.existe = existe

    def transaction(self):
        return _Cursor(self.existe)  # solo se usa como context manager

    def cursor(self):
        return _Cursor(self.existe)


@pytest.fixture
def salida_logs(monkeypatch):
    """Captura lo que escribiría el handler JSON, sin depender de capsys."""
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "clave-de-prueba")
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    raiz = logging.getLogger()
    raiz.addHandler(handler)
    yield buffer
    raiz.removeHandler(handler)
    app.dependency_overrides.clear()


def _eventos(buffer) -> list[dict]:
    return [json.loads(x) for x in buffer.getvalue().splitlines() if x.strip()]


def _datos(**extra):
    return {
        "rut": RUT,
        "name": NOMBRE,
        "email": EMAIL,
        "phone": TELEFONO,
        "address": DIRECCION,
        "has_consent": True,
        **extra,
    }


def _sin_pii(buffer):
    crudo = buffer.getvalue()
    for dato in (NOMBRE, "Ana Soto", EMAIL, "8765 4321", DIRECCION, RUT, RUT_BODY):
        assert dato not in crudo, f"PII en el log: {dato}"


def test_201_registra_evento_sin_pii_y_con_id_intacto(salida_logs):
    app.dependency_overrides[get_conn] = lambda: _Conn(existe=False)
    r = TestClient(app).post("/api/v1/patients", json=_datos())
    assert r.status_code == 201

    eventos = _eventos(salida_logs)
    creado = next(e for e in eventos if e["message"] == "patient_created")
    assert creado["patient_id"] == r.json()["patient_id"]  # el UUID no se altera
    assert creado["has_contact_data"] is True
    completado = next(e for e in eventos if e["message"] == "request_completed")
    assert completado["path"] == "/api/v1/patients" and completado["status"] == 201
    assert completado["request_id"] == creado["request_id"] != "-"
    _sin_pii(salida_logs)


def test_409_no_loguea_el_rut_pero_la_respuesta_no_cambia(salida_logs):
    app.dependency_overrides[get_conn] = lambda: _Conn(existe=True)
    r = TestClient(app).post("/api/v1/patients", json=_datos())
    assert r.status_code == 409
    assert RUT in r.json()["detail"]  # contrato de la API intacto

    mensajes = [e["message"] for e in _eventos(salida_logs)]
    assert "patient_create_conflict" in mensajes and "http_error" in mensajes
    _sin_pii(salida_logs)


def test_422_loguea_solo_nombres_de_campo(salida_logs):
    app.dependency_overrides[get_conn] = lambda: _Conn()  # FastAPI resuelve la conexión antes de validar
    r = TestClient(app).post("/api/v1/patients", json=_datos(rut="11.111.111-2"))
    assert r.status_code == 422
    assert "dígito verificador" in r.json()["errors"][0]["message"]  # respuesta intacta

    fallo = next(e for e in _eventos(salida_logs) if e["message"] == "validation_failed")
    assert fallo["fields"] == ["rut"]
    assert "dígito verificador" not in salida_logs.getvalue()
    assert "11.111.111" not in salida_logs.getvalue()
    _sin_pii(salida_logs)


def test_error_no_controlado_registra_tipo_sin_mensaje(salida_logs):
    def _explota():
        raise RuntimeError(f"fallo con {RUT} {EMAIL}")

    app.dependency_overrides[get_conn] = _explota
    r = TestClient(app, raise_server_exceptions=False).post("/api/v1/patients", json=_datos())
    assert r.status_code == 500

    fallo = next(e for e in _eventos(salida_logs) if e["message"] == "request_failed")
    assert fallo["error_type"] == "RuntimeError"
    _sin_pii(salida_logs)
