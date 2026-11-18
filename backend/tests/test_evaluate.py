"""Pruebas de POST /triage/{episodio_id}/evaluate (S09-7) sin base de datos ni internet.

La conexión es un falso que responde lo que lee el endpoint y guarda lo que inserta;
el motor de IA se reemplaza por una función falsa (el motor real ya se prueba en
test_ai_engine.py). Las pruebas contra Postgres real están en test_evaluate_db.py.
"""
import contextlib
import logging
import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.ai import engine
from app.ai.contrato import ClasificacionIA, EntradaIA
from app.ai.reglas import MODELO_RESPALDO
from app.core.security import crear_token
from app.db import get_conn
from app.main import app

client = TestClient(app)

EPISODIO = uuid.uuid4()
PACIENTE = uuid.uuid4()
SIGNOS = (120, 80, 110, 18, 37.2, 98.0, 4, "alerta")  # saturación llega como float
FECHA_NAC = date(1980, 1, 1)


def _cabecera(rol="enfermero") -> dict:
    return {"Authorization": f"Bearer {crear_token(uuid.uuid4(), rol)[0]}"}


class _Cursor:
    def __init__(self, bd):
        self.bd = bd
        self.sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params or {}
        self.bd.consultas.append(sql)
        if "INSERT INTO clasificacion_ia" in sql:
            self.bd.insertados.append(self.params)

    def fetchone(self):
        sql, bd = self.sql, self.bd
        if "FROM usuario_staff" in sql:
            return (1,)
        if "FROM episodio_triage" in sql:
            return bd.episodio
        if "FROM paciente" in sql:
            return bd.paciente
        if "FROM signos_vitales" in sql:
            return bd.signos
        if "FROM clasificacion_ia" in sql:
            return bd.previa
        return None

    def fetchall(self):
        return self.bd.sintomas if "FROM sintomas_triage" in self.sql else []


class _BD:
    """Estado de la base falsa y conexión en uno."""

    def __init__(self):
        self.episodio = (PACIENTE, "dolor de pecho desde ayer")
        self.paciente = (FECHA_NAC, "femenino")
        self.signos = SIGNOS
        self.sintomas = [("dolor_toracico", "moderada", 5)]
        self.previa = None
        self.consultas = []
        self.insertados = []

    def transaction(self):
        return contextlib.nullcontext()

    def cursor(self):
        return _Cursor(self)


@pytest.fixture
def bd():
    base = _BD()
    app.dependency_overrides[get_conn] = lambda: base
    yield base
    app.dependency_overrides.clear()


@pytest.fixture
def motor(monkeypatch):
    """Motor falso: guarda la entrada recibida y devuelve `resultado`."""

    class Falso:
        llamadas = []
        resultado = ClasificacionIA(
            nivel_esi_sugerido=2,
            justificacion="Dolor torácico con taquicardia leve: no debe esperar.",
            modelo_usado="claude-haiku-5-5",
            latencia_ms=900,
            fallback_aplicado=False,
        )

    def clasificar(entrada):
        Falso.llamadas.append(entrada)
        return Falso.resultado

    monkeypatch.setattr(engine, "clasificar", clasificar)
    return Falso


def _evaluar(**kw):
    kw.setdefault("headers", _cabecera())
    return client.post(f"/api/v1/triage/{EPISODIO}/evaluate", **kw)


def test_201_guarda_y_responde_con_el_schema_clasificacion_ia(bd, motor):
    r = _evaluar()
    assert r.status_code == 201, r.text
    b = r.json()
    assert set(b) == {
        "clasificacion_id", "episodio_id", "nivel_esi_sugerido", "justificacion_ia",
        "modelo_usado", "fallback_aplicado", "latencia_ms", "fecha_hora_solicitud",
    }
    assert b["episodio_id"] == str(EPISODIO)
    assert b["nivel_esi_sugerido"] == 2 and b["fallback_aplicado"] is False
    assert b["modelo_usado"] == "claude-haiku-5-5"
    assert b["latencia_ms"] >= 0

    (fila,) = bd.insertados
    assert fila["clasificacion_id"] == uuid.UUID(b["clasificacion_id"])
    assert fila["nivel"] == 2 and fila["fallback"] is False
    assert len(fila["hash"]) == 64
    assert fila["tiempo_respuesta"] >= fila["tiempo_solicitud"]
    assert fila["idempotency_key"] is None
    assert isinstance(fila["token"], uuid.UUID) and fila["token"] != PACIENTE


def test_el_payload_a_la_ia_no_lleva_datos_personales(bd, motor):
    _evaluar()
    (entrada,) = motor.llamadas
    assert isinstance(entrada, EntradaIA)
    assert set(entrada.model_dump()) == {
        "edad_anios", "sexo_biologico", "signos_vitales", "sintomas", "motivo_consulta",
    }
    hoy = date.today()
    esperada = hoy.year - 1980 - ((hoy.month, hoy.day) < (1, 1))
    assert entrada.edad_anios in (esperada, esperada - 1)  # por el cambio de día en UTC
    assert entrada.signos_vitales.saturacion_oxigeno == 98
    assert entrada.sintomas[0].codigo_sintoma == "dolor_toracico"
    # Nunca se consultan nombre, RUT ni contactos.
    leido = " ".join(bd.consultas).lower()
    for prohibido in ("nombre_completo", "rut", "contacto_", "email", "telefono"):
        assert prohibido not in leido


def test_si_el_motor_usa_el_respaldo_se_guarda_fallback_aplicado(bd, motor):
    motor.resultado = ClasificacionIA(
        nivel_esi_sugerido=3,
        justificacion="Clasificación por reglas de respaldo (sin IA): dolor 4/10.",
        modelo_usado=MODELO_RESPALDO,
        latencia_ms=1500,
        fallback_aplicado=True,
    )
    r = _evaluar()
    assert r.status_code == 201
    assert r.json()["fallback_aplicado"] is True
    assert r.json()["modelo_usado"] == MODELO_RESPALDO
    assert bd.insertados[0]["fallback"] is True
    assert bd.insertados[0]["modelo"] == MODELO_RESPALDO


def test_episodio_inexistente_404_problem_json(bd, motor):
    bd.episodio = None
    r = _evaluar()
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert motor.llamadas == [] and bd.insertados == []


def test_sin_fecha_de_nacimiento_422_y_no_llama_a_la_ia(bd, motor):
    bd.paciente = (None, "femenino")
    r = _evaluar()
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert motor.llamadas == [] and bd.insertados == []


def test_sin_signos_vitales_422(bd, motor):
    bd.signos = None
    assert _evaluar().status_code == 422
    assert motor.llamadas == []


def test_idempotency_key_invalida_422(bd, motor):
    r = _evaluar(headers={**_cabecera(), "Idempotency-Key": "no-es-uuid"})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert motor.llamadas == []


def test_idempotency_key_repetida_devuelve_lo_guardado_sin_llamar_a_la_ia(bd, motor):
    antes = datetime(2026, 11, 18, 12, 0, 0)
    bd.previa = (uuid.uuid4(), 4, "Respuesta guardada antes del reintento.", "claude-haiku-5-5",
                 False, antes, antes + timedelta(milliseconds=700))
    r = _evaluar(headers={**_cabecera(), "Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 201
    assert r.json()["nivel_esi_sugerido"] == 4 and r.json()["latencia_ms"] == 700
    assert motor.llamadas == [] and bd.insertados == []


def test_la_clave_se_guarda_con_la_clasificacion(bd, motor):
    clave = uuid.uuid4()
    assert _evaluar(headers={**_cabecera(), "Idempotency-Key": str(clave)}).status_code == 201
    assert bd.insertados[0]["idempotency_key"] == clave


def test_sin_token_401_y_medico_403(bd, motor):
    assert client.post(f"/api/v1/triage/{EPISODIO}/evaluate").status_code == 401
    assert _evaluar(headers=_cabecera("medico")).status_code == 403
    assert motor.llamadas == []


def test_los_logs_no_llevan_pii_ni_texto_de_sintomas(bd, motor, caplog):
    with caplog.at_level(logging.DEBUG):
        _evaluar()
    texto = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    for prohibido in ("dolor_toracico", "dolor de pecho", "Dolor torácico", str(PACIENTE), "1980"):
        assert prohibido not in texto
