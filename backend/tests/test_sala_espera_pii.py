"""Pantalla pública: ningún dato personal en el JSON de la respuesta (S11-11, US-04).

Sin base de datos. La conexión es falsa y se revisa TODO el texto de la respuesta buscando
patrones de RUT, correo y teléfono. También se comprueba que, si alguien agregara un dato
personal a la fila, la API falla (500) en vez de publicarlo.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import sala_espera as endpoint
from app.core.sanitizer import sanitize_symptoms_text
from app.db import get_conn_sala_espera
from app.main import app
from tests.pii import buscar_pii

URL = "/api/v1/sala-espera"

FILAS = [
    ("A", 12, 1, "en_atencion", None, 9),
    ("A", 15, 2, "en_espera", 1, 20),
    ("A", 16, 3, "en_espera", 2, 75),
    ("B", 912, 5, "en_espera", 3, 1_250_412),  # un episodio muy antiguo: número grande de minutos
]


class _Cursor:
    def __init__(self, filas):
        self.filas = filas

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.filas


class _Conexion:
    def __init__(self, filas):
        self.filas = filas

    def cursor(self):
        return _Cursor(self.filas)


@pytest.fixture
def sala(monkeypatch):
    app.dependency_overrides[get_conn_sala_espera] = lambda: _Conexion(FILAS)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_conn_sala_espera, None)


# --- El detector funciona (si no, "no encontré nada" no probaría nada) ----------------------


@pytest.mark.parametrize(
    "texto, tipo",
    [
        ("12.345.678-5", "RUT"),
        ("12345678-5", "RUT"),
        ("1.234.567-K", "RUT"),
        ("9.876.543 - 2", "RUT"),
        ('"rut":"19.876.543-2"', "RUT"),
        ("juan.perez@correo.cl", "correo"),
        ("a_b+c@mail.example.com", "correo"),
        ("+56912345678", "telefono"),
        ("+56 9 1234 5678", "telefono"),
        ("912345678", "telefono"),
        ("9 8765-4321", "telefono"),
        ("221234567", "telefono"),
    ],
)
def test_el_detector_encuentra_cada_tipo_de_dato(texto, tipo):
    assert tipo in {t for t, _ in buscar_pii(texto)}


@pytest.mark.parametrize(
    "texto",
    [
        '[{"turno":"A-12","nivel_esi":2,"estado":"en_espera","posicion":1,'
        '"minutos_espera":20,"tiempo_estimado_min":0}]',
        '{"minutos_espera":1250412,"tiempo_estimado_min":176}',
        "Turno B-912",
        "2026-11-22T10:30:00",
    ],
)
def test_el_detector_no_acusa_una_respuesta_normal(texto):
    assert buscar_pii(texto) == []


def test_el_detector_coincide_con_el_sanitizador_de_la_app():
    """Lo que el sanitizador de S09 enmascara, el detector también lo ve."""
    texto = "RUT 19.876.543-2, teléfono +56912345678 y correo juan.perez@email.com"
    assert sanitize_symptoms_text(texto) != texto
    assert {t for t, _ in buscar_pii(texto)} == {"RUT", "telefono", "correo"}


# --- La respuesta de la sala -------------------------------------------------------------


def test_todo_el_json_de_la_sala_esta_libre_de_rut_correo_y_telefono(sala):
    r = sala.get(URL)
    assert r.status_code == 200, r.text
    assert len(r.json()) == len(FILAS)
    assert buscar_pii(r.text) == []
    # El sanitizador de la app tampoco encuentra nada que enmascarar en toda la respuesta.
    assert sanitize_symptoms_text(r.text) == r.text


def test_la_respuesta_no_trae_ningun_texto_libre(sala):
    """Todos los valores son números, estados o turnos con forma fija: no hay texto libre."""
    for fila in sala.get(URL).json():
        for clave, valor in fila.items():
            if clave == "turno":
                assert len(valor) <= 6 and valor[1] == "-"
            elif clave == "estado":
                assert valor in {"en_espera", "en_atencion"}
            else:
                assert valor is None or isinstance(valor, int)


# --- Si algo personal llegara a la fila, la API falla en vez de publicarlo -----------------


def test_un_campo_personal_extra_en_la_fila_da_500_y_no_se_publica(sala, monkeypatch):
    def fila_con_datos_personales(*_args):
        return {
            "turno": "A-1",
            "nivel_esi": 2,
            "estado": "en_espera",
            "posicion": 1,
            "minutos_espera": 0,
            "tiempo_estimado_min": 15,
            "rut": "12.345.678-5",
            "nombre": "Ana Soto",
        }

    monkeypatch.setattr(endpoint, "construir_fila", fila_con_datos_personales)
    r = sala.get(URL)
    assert r.status_code == 500
    assert "12.345.678-5" not in r.text and "Ana Soto" not in r.text


@pytest.mark.parametrize("turno", ["12.345.678-5", "Ana Soto", "juan@correo.cl", "+56912345678"])
def test_un_turno_con_datos_personales_no_pasa_el_esquema(sala, monkeypatch, turno):
    def fila_con_turno_personal(*_args):
        return {
            "turno": turno,
            "nivel_esi": 2,
            "estado": "en_espera",
            "posicion": 1,
            "minutos_espera": 0,
            "tiempo_estimado_min": 15,
        }

    monkeypatch.setattr(endpoint, "construir_fila", fila_con_turno_personal)
    r = sala.get(URL)
    assert r.status_code == 500
    assert turno not in json.dumps(r.text)
