"""S11-1: límite de peticiones (429), headers de seguridad, CORS y reload solo en desarrollo.

No necesitan base de datos: el login usa una conexión falsa y /triage/cola revisa el rol
antes de abrir la conexión.
"""
import contextlib
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import LimitadorMemoria, ip_cliente, parsear_limite
from app.core.security import crear_token
from app.core.seguridad_http import origenes_cors
from app.db import get_conn_login
from app.main import app, usar_reload

LOGIN = "/api/v1/auth/login"
COLA = "/api/v1/triage/cola"
CREDENCIALES = {"email": "nadie@meditriage.test", "password": "Incorrecta-2026!"}


class _SinUsuarios:
    """Conexión falsa: ningún correo existe, así que todo login es 401."""

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return None

    def transaction(self):
        return contextlib.nullcontext()


@pytest.fixture
def client():
    app.dependency_overrides[get_conn_login] = lambda: _SinUsuarios()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _cabecera(rol: str, usuario_id=None) -> dict:
    token, _ = crear_token(usuario_id or uuid.uuid4(), rol)
    return {"Authorization": f"Bearer {token}"}


# --- Límite de peticiones -----------------------------------------------------------------


def test_login_supera_el_limite_y_recibe_429(client, monkeypatch):
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "clave-de-cifrado-de-pruebas")
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "3/minute")

    for _ in range(3):
        assert client.post(LOGIN, json=CREDENCIALES).status_code == 401

    r = client.post(LOGIN, json=CREDENCIALES)
    assert r.status_code == 429
    assert r.headers["content-type"].startswith("application/problem+json")
    assert int(r.headers["retry-after"]) >= 1
    cuerpo = r.json()
    assert cuerpo["status"] == 429
    assert cuerpo["title"] == "Demasiadas peticiones"
    assert cuerpo["instance"] == LOGIN


def test_triage_supera_el_limite_por_usuario_y_recibe_429(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TRIAGE", "2/minute")
    # Un auditor recibe 403 en la cola sin tocar la base, pero igual consume su cupo.
    usuario = _cabecera("auditor")

    assert client.get(COLA, headers=usuario).status_code == 403
    assert client.get(COLA, headers=usuario).status_code == 403

    r = client.get(COLA, headers=usuario)
    assert r.status_code == 429
    assert "retry-after" in r.headers

    # Otro usuario tiene su propio contador.
    assert client.get(COLA, headers=_cabecera("auditor")).status_code == 403


def test_triage_sin_token_responde_401_y_no_consume_cupo(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TRIAGE", "1/minute")
    for _ in range(3):
        assert client.get(COLA).status_code == 401


def test_limite_desactivado(client, monkeypatch):
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "clave-de-cifrado-de-pruebas")
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "1/minute")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    for _ in range(3):
        assert client.post(LOGIN, json=CREDENCIALES).status_code == 401


def test_la_ventana_se_libera_con_el_tiempo():
    ahora = [1000.0]
    limitador = LimitadorMemoria(reloj=lambda: ahora[0])

    assert limitador.intentar("k", 2, 60) is None
    assert limitador.intentar("k", 2, 60) is None
    assert limitador.intentar("k", 2, 60) == pytest.approx(60)

    ahora[0] += 61
    assert limitador.intentar("k", 2, 60) is None


@pytest.mark.parametrize(
    "texto, esperado",
    [("10/minute", (10, 60)), ("5/second", (5, 1)), ("100/hours", (100, 3600)), ("1/day", (1, 86400))],
)
def test_parsear_limite(texto, esperado):
    assert parsear_limite(texto) == esperado


@pytest.mark.parametrize("texto", ["10", "abc/minute", "0/minute", "10/semana"])
def test_parsear_limite_invalido(texto):
    with pytest.raises(ValueError):
        parsear_limite(texto)


class _Peticion:
    def __init__(self, xff=None, host="10.0.0.9"):
        self.headers = {"x-forwarded-for": xff} if xff else {}
        self.client = type("C", (), {"host": host})()


def test_ip_cliente_ignora_x_forwarded_for_sin_proxy_de_confianza(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert ip_cliente(_Peticion(xff="1.2.3.4")) == "10.0.0.9"


def test_ip_cliente_con_un_proxy_toma_la_ultima_ip(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    # "6.6.6.6" la inventó el cliente; "1.2.3.4" la agregó el proxy de confianza.
    assert ip_cliente(_Peticion(xff="6.6.6.6, 1.2.3.4")) == "1.2.3.4"


# --- Headers de seguridad -----------------------------------------------------------------


def test_headers_de_seguridad_en_la_api(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "max-age=" in r.headers["strict-transport-security"]
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert "permissions-policy" in r.headers


def test_headers_de_seguridad_tambien_en_errores_y_429(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TRIAGE", "1/minute")
    usuario = _cabecera("auditor")
    client.get(COLA, headers=usuario)
    r = client.get(COLA, headers=usuario)
    assert r.status_code == 429
    assert r.headers["x-content-type-options"] == "nosniff"


def test_sin_hsts_en_desarrollo(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    r = client.get("/api/v1/health")
    assert "strict-transport-security" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_docs_tiene_una_csp_que_permite_swagger(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "cdn.jsdelivr.net" in r.headers["content-security-policy"]


# --- CORS ---------------------------------------------------------------------------------


def _preflight(client, origen):
    return client.options(
        LOGIN,
        headers={"Origin": origen, "Access-Control-Request-Method": "POST"},
    )


def test_cors_acepta_el_origen_del_frontend(client):
    origen = origenes_cors()[0]
    r = _preflight(client, origen)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origen
    assert r.headers["access-control-allow-credentials"] == "true"


def test_cors_rechaza_otro_origen(client):
    r = _preflight(client, "https://sitio-malicioso.example")
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers

    r = client.get("/api/v1/health", headers={"Origin": "https://sitio-malicioso.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_no_admite_comodin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        origenes_cors()


# --- reload -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valor, esperado",
    [("development", True), ("Development", True), ("production", False), ("staging", False)],
)
def test_reload_solo_en_desarrollo(monkeypatch, valor, esperado):
    monkeypatch.setenv("ENVIRONMENT", valor)
    assert usar_reload() is esperado


def test_reload_desactivado_si_no_hay_environment(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert usar_reload() is False
