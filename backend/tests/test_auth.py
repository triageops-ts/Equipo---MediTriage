"""Login con roles: login válido, inválido (401) y rol incorrecto (403).

No necesitan base de datos: la búsqueda del usuario se reemplaza por una conexión falsa.
"""
import contextlib
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import COOKIE_NOMBRE, crear_token, hash_password, leer_token
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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "clave-de-cifrado-de-pruebas")
    usuarios = {EMAIL: (USUARIO_ID, "enfermero", hash_password(PASSWORD))}
    app.dependency_overrides[get_conn] = lambda: _Conexion(usuarios)
    app.dependency_overrides[get_conn_login] = lambda: _Conexion(usuarios)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# --- Login --------------------------------------------------------------------------------


def test_login_valido_devuelve_token_con_rol_y_usuario_id(client):
    r = _login(client)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["token_type"] == "bearer" and b["rol"] == "enfermero"
    assert b["usuario_id"] == str(USUARIO_ID) and b["expires_in"] > 0

    usuario = leer_token(b["access_token"])
    assert usuario.usuario_id == USUARIO_ID and usuario.rol == "enfermero"


def test_login_valido_guarda_cookie_httponly_samesite_strict(client):
    r = _login(client)
    cookie = r.headers["set-cookie"].lower()
    assert f"{COOKIE_NOMBRE}=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert r.cookies.get(COOKIE_NOMBRE) == r.json()["access_token"]


def test_login_con_correo_en_mayusculas_y_espacios(client):
    assert _login(client, email="  ENFERMERO@MediTriage.test ").status_code == 200


def test_login_password_incorrecta_401(client):
    r = _login(client, password="otra-clave")
    assert r.status_code == 401
    assert COOKIE_NOMBRE not in r.headers.get("set-cookie", "")


def test_login_usuario_inexistente_401_con_el_mismo_mensaje(client):
    a = _login(client, email="nadie@meditriage.test")
    b = _login(client, password="otra-clave")
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_login_usuario_sin_password_hash_401(client):
    app.dependency_overrides[get_conn_login] = lambda: _Conexion(
        {EMAIL: (USUARIO_ID, "enfermero", None)}
    )
    assert _login(client).status_code == 401


def test_login_cuerpo_invalido_422(client):
    assert client.post("/api/v1/auth/login", json={"email": "sin-arroba", "password": "x"}).status_code == 422
    assert client.post("/api/v1/auth/login", json={"email": EMAIL}).status_code == 422


def test_la_contrasena_no_se_guarda_en_texto_plano():
    h = hash_password(PASSWORD)
    assert PASSWORD not in h and h.startswith("$2")


# --- usuario_actual: 401 --------------------------------------------------------------------

PROTEGIDOS = [
    ("get", "/api/v1/patients?rut=11.111.111-1"),
    ("post", "/api/v1/patients"),
    ("post", "/api/v1/triage/formulario"),
    ("post", f"/api/v1/triage/{uuid.uuid4()}/decision"),
    ("get", "/api/v1/auth/me"),
]


@pytest.mark.parametrize("metodo,ruta", PROTEGIDOS)
def test_sin_token_401(client, metodo, ruta):
    r = getattr(client, metodo)(ruta)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_health_y_login_no_piden_token(client):
    assert client.get("/api/v1/health").status_code == 200
    assert _login(client).status_code == 200


@pytest.mark.parametrize("token", ["basura", "a.b.c"])
def test_token_invalido_401(client, token):
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_expirado_401(client, monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "-1")
    token, _ = crear_token(USUARIO_ID, "enfermero")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_firmado_con_otra_clave_401(client):
    falso = jwt.encode({"sub": str(USUARIO_ID), "rol": "medico", "exp": 4_000_000_000}, "otra-clave" * 5, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_sin_firma_alg_none_401(client):
    falso = jwt.encode({"sub": str(USUARIO_ID), "rol": "medico", "exp": 4_000_000_000}, None, algorithm="none")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_con_rol_desconocido_401(client):
    token = jwt.encode(
        {"sub": str(USUARIO_ID), "rol": "superadmin", "exp": 4_000_000_000},
        "clave-de-pruebas-0123456789-0123456789-abcdef",
        algorithm="HS256",
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# --- Cookie o Bearer ------------------------------------------------------------------------


def test_usuario_actual_acepta_la_cookie(client):
    assert _login(client).status_code == 200  # el cliente guarda la cookie
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json() == {"usuario_id": str(USUARIO_ID), "rol": "enfermero"}


def test_usuario_actual_acepta_el_header_bearer(client):
    token, _ = crear_token(USUARIO_ID, "medico")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["rol"] == "medico"


def test_logout_borra_la_cookie(client):
    _login(client)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


# --- Rol incorrecto: 403 --------------------------------------------------------------------


def _bearer(rol):
    return {"Authorization": f"Bearer {crear_token(uuid.uuid4(), rol)[0]}"}


@pytest.mark.parametrize("rol", ["medico", "auditor"])
def test_registrar_paciente_con_rol_incorrecto_403(client, rol):
    r = client.post("/api/v1/patients", json={}, headers=_bearer(rol))
    assert r.status_code == 403


@pytest.mark.parametrize("rol", ["medico", "auditor"])
def test_formulario_y_decision_con_rol_incorrecto_403(client, rol):
    h = _bearer(rol)
    assert client.post("/api/v1/triage/formulario", json={}, headers=h).status_code == 403
    r = client.post(f"/api/v1/triage/{uuid.uuid4()}/decision", json={}, headers=h)
    assert r.status_code == 403


def test_auditor_no_puede_buscar_pacientes_403(client):
    r = client.get("/api/v1/patients?rut=11.111.111-1", headers=_bearer("auditor"))
    assert r.status_code == 403


def test_el_rol_correcto_pasa_el_control_de_rol(client):
    # Con el rol correcto ya no es 401/403 (aquí falla por el cuerpo vacío: 422).
    r = client.post("/api/v1/triage/formulario", json={}, headers=_bearer("enfermero"))
    assert r.status_code == 422


def test_usuario_id_en_el_cuerpo_se_rechaza_422(client):
    r = client.post(
        f"/api/v1/triage/{uuid.uuid4()}/decision",
        json={"nivel_esi_final": 3, "usuario_id": str(uuid.uuid4())},
        headers=_bearer("enfermero"),
    )
    assert r.status_code == 422
