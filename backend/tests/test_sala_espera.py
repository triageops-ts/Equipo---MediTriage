"""GET /sala-espera sin base de datos (S11-10, US-04).

La conexión se reemplaza por una falsa para revisar que el endpoint es público, que la
respuesta solo trae los campos del contrato y que el límite por IP funciona.
Las pruebas de orden y de RLS contra una base real están en test_sala_espera_db.py.
"""
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db import get_conn_sala_espera
from app.main import app
from app.schemas.sala_espera import (
    TIEMPO_OBJETIVO_MIN,
    SalaEsperaEntry,
    formatear_turno,
    tiempo_estimado,
)

client = TestClient(app)
URL = "/api/v1/sala-espera"

CAMPOS = {"turno", "nivel_esi", "estado", "posicion", "minutos_espera", "tiempo_estimado_min"}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

# (letra, numero, nivel_esi, estado, posicion, minutos_espera), como las devuelve la consulta.
FILAS = [
    ("A", 12, 2, "en_atencion", None, 9),
    ("A", 15, 3, "en_espera", 1, 20),
    ("A", 16, 3, "en_espera", 2, 75),
    ("B", 18, 5, "en_espera", 3, 4),
]


class _CursorFalso:
    def __init__(self, filas):
        self.filas = filas
        self.ejecutadas = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.ejecutadas.append((sql, params))

    def fetchall(self):
        return self.filas


class _ConexionFalsa:
    def __init__(self, filas):
        self.cur = _CursorFalso(filas)

    def cursor(self):
        return self.cur


@pytest.fixture
def conexion_falsa():
    conn = _ConexionFalsa(FILAS)
    app.dependency_overrides[get_conn_sala_espera] = lambda: conn
    yield conn
    app.dependency_overrides.pop(get_conn_sala_espera, None)


# --- Endpoint -----------------------------------------------------------------------


def test_publico_sin_token_200(conexion_falsa):
    r = client.get(URL)
    assert r.status_code == 200, r.text
    assert len(r.json()) == len(FILAS)


def test_un_token_invalido_no_importa(conexion_falsa):
    r = client.get(URL, headers={"Authorization": "Bearer token-que-no-sirve"})
    assert r.status_code == 200


def test_solo_campos_del_contrato_sin_ids(conexion_falsa):
    r = client.get(URL)
    for fila in r.json():
        assert set(fila) == CAMPOS
    texto = r.text
    for prohibido in ("episodio_id", "patient_id", "paciente_id", "rut", "nombre", "name"):
        assert prohibido not in texto
    assert not UUID_RE.search(texto)


def test_turno_y_tiempos(conexion_falsa):
    filas = client.get(URL).json()
    assert [f["turno"] for f in filas] == ["A-12", "A-15", "A-16", "B-18"]
    # En atención: 0 y sin posición.
    assert filas[0]["posicion"] is None
    assert filas[0]["tiempo_estimado_min"] == 0
    # ESI 3 (objetivo 60): 20 esperados -> faltan 40; 75 esperados -> 0 (ya cumplió).
    assert filas[1]["tiempo_estimado_min"] == 40
    assert filas[2]["tiempo_estimado_min"] == 0
    # ESI 5 (objetivo 180): 4 esperados -> faltan 176.
    assert filas[3]["tiempo_estimado_min"] == 176


def test_respeta_el_orden_de_la_consulta(conexion_falsa):
    filas = client.get(URL).json()
    assert [f["posicion"] for f in filas if f["estado"] == "en_espera"] == [1, 2, 3]


def test_pide_solo_estados_abiertos_con_tope(conexion_falsa):
    client.get(URL)
    sql, params = conexion_falsa.cur.ejecutadas[0]
    assert params["estados"] == ["en_espera", "en_atencion"]
    assert params["limit"] == 100
    # La consulta nunca lee datos personales ni el texto libre.
    for columna in ("nombre_completo", "rut", "paciente", "motivo_consulta"):
        assert columna not in sql


def test_no_se_guarda_en_cache(conexion_falsa):
    assert client.get(URL).headers["cache-control"] == "no-store"


def test_limite_por_ip_429(conexion_falsa, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_SALA_ESPERA", "2/minute")
    assert client.get(URL).status_code == 200
    assert client.get(URL).status_code == 200
    r = client.get(URL)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1


def test_solo_get(conexion_falsa):
    assert client.post(URL).status_code == 405


# --- Reglas de negocio ----------------------------------------------------------------


def test_formatear_turno():
    assert formatear_turno("A", 1) == "A-1"
    assert formatear_turno("Z", 127) == "Z-127"


@pytest.mark.parametrize(
    "nivel, estado, minutos, esperado",
    [
        (1, "en_espera", 0, 0),
        (2, "en_espera", 5, 10),
        (3, "en_espera", 0, 60),
        (4, "en_espera", 100, 20),
        (5, "en_espera", 30, 150),
        (5, "en_espera", 999, 0),
        (2, "en_atencion", 1, 0),
        (None, "en_atencion", 1, 0),
        (None, "en_espera", 10, None),
    ],
)
def test_tiempo_estimado(nivel, estado, minutos, esperado):
    assert tiempo_estimado(nivel, estado, minutos) == esperado


def test_objetivos_cubren_los_cinco_niveles():
    assert sorted(TIEMPO_OBJETIVO_MIN) == [1, 2, 3, 4, 5]
    objetivos = [TIEMPO_OBJETIVO_MIN[n] for n in range(1, 6)]
    assert objetivos == sorted(objetivos)


def test_esquema_rechaza_campos_extra():
    with pytest.raises(ValidationError):
        SalaEsperaEntry(
            turno="A-1",
            nivel_esi=2,
            estado="en_espera",
            posicion=1,
            minutos_espera=0,
            tiempo_estimado_min=15,
            episodio_id="550e8400-e29b-41d4-a716-446655440000",
        )


def test_esquema_rechaza_turno_mal_formado():
    with pytest.raises(ValidationError):
        SalaEsperaEntry(
            turno="Ana Soto", nivel_esi=3, estado="en_espera", minutos_espera=0,
            tiempo_estimado_min=60,
        )


def test_esquema_exige_nivel_confirmado():
    with pytest.raises(ValidationError):
        SalaEsperaEntry(
            turno="A-1", nivel_esi=None, estado="en_espera", minutos_espera=0,
            tiempo_estimado_min=None,
        )
