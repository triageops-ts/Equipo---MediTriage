"""Fixtures base para pruebas BDD (pytest-bdd) con datos sintéticos (S09-5)."""
import os
import uuid
from collections.abc import Callable, Generator

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.core.security import crear_token
from app.main import app


def _obtener_db_url_segura() -> str:
    """Obtiene una URL de BD de pruebas y bloquea si parece apuntar a producción."""
    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("Se requiere TEST_DATABASE_URL o DATABASE_URL para pruebas BDD con BD.")

    if any(marca in db_url.lower() for marca in ("prod", "production")):
        pytest.fail("Bloqueado por seguridad: no ejecutar pruebas BDD contra producción.")

    return db_url


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Cliente de pruebas FastAPI reutilizable en la sesión de BDD."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> Callable[[str, uuid.UUID | None], dict[str, str]]:
    """Genera cabecera Authorization Bearer con datos sintéticos para el rol indicado."""

    def _headers(rol: str = "enfermero", user_id: uuid.UUID | None = None) -> dict[str, str]:
        token_result = crear_token(user_id or uuid.uuid4(), rol)
        token = token_result[0] if isinstance(token_result, tuple) else token_result
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def db_conn() -> Generator[psycopg.Connection, None, None]:
    """Conexión aislada a BD con rollback automático al finalizar cada prueba."""
    db_url = _obtener_db_url_segura()
    with psycopg.connect(db_url) as conn:
        conn.autocommit = False
        try:
            yield conn
        finally:
            conn.rollback()


@pytest.fixture
def synthetic_vitals_complete() -> dict[str, object]:
    """Payload sintético completo de signos vitales y síntomas (caso feliz)."""
    return {
        "temperatura_c": 36.8,
        "frecuencia_cardiaca": 78,
        "frecuencia_respiratoria": 16,
        "presion_sistolica": 120,
        "presion_diastolica": 80,
        "saturacion_o2": 98,
        "sintomas": ["cefalea leve sin signos de alarma"],
    }


@pytest.fixture
def synthetic_vitals_partial() -> dict[str, object]:
    """Payload sintético parcial (solo temperatura y frecuencia cardíaca)."""
    return {
        "temperatura_c": 37.2,
        "frecuencia_cardiaca": 84,
    }


@pytest.fixture
def synthetic_vitals_invalid() -> dict[str, object]:
    """Payload sintético con valor fuera de rango (temperatura = -5°C)."""
    return {
        "temperatura_c": -5.0,
        "frecuencia_cardiaca": 80,
    }
