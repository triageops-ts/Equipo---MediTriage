"""Pruebas del canal en tiempo real (Redis Pub/Sub).

- Las pruebas "unitarias" no necesitan Redis ni Postgres: reemplazan solo el cliente de
  Redis o la conexión a la base (mocks acotados a pruebas unitarias).
- La prueba "de integración" usa el Redis real del docker-compose y se omite si no hay
  REDIS_URL, igual que las pruebas de base de datos se omiten sin DATABASE_URL.
"""
import contextlib
import json
import os
import uuid
from datetime import datetime

import pytest
import redis
from fastapi.testclient import TestClient

from app.api.v1.endpoints import triage as triage_endpoint
from app.core import realtime
from app.db import get_conn
from app.main import app

client = TestClient(app)

FECHA_DECISION = datetime(2026, 11, 13, 20, 0, 0)


@pytest.fixture(autouse=True)
def _limpiar(monkeypatch):
    # Cada prueba parte sin cliente de Redis creado y sin conexiones falsas.
    monkeypatch.setattr(realtime, "_cliente", None)
    yield
    app.dependency_overrides.clear()


# --- Unitarias del módulo realtime -----------------------------------------------------


class _ClienteFalso:
    def __init__(self, error=None):
        self.error = error
        self.mensajes = []

    def publish(self, canal, mensaje):
        if self.error:
            raise self.error
        self.mensajes.append((canal, mensaje))


def test_construir_evento_tiene_el_formato_del_catalogo():
    ev = realtime.construir_evento("triage.evaluacion.confirmada", {"a": 1})
    assert set(ev) == {"event_id", "event_type", "version", "timestamp", "producer", "data"}
    assert ev["event_id"].startswith("evt_")
    assert ev["event_type"] == "triage.evaluacion.confirmada"
    assert ev["version"] == "1.0"
    assert ev["producer"] == "triage-service"
    assert ev["timestamp"].endswith("Z")
    assert ev["data"] == {"a": 1}


def test_publicar_evento_envia_json_al_canal_de_triage(monkeypatch):
    falso = _ClienteFalso()
    monkeypatch.setattr(realtime, "_cliente_redis", lambda: falso)

    assert realtime.publicar_evento("triage.evaluacion.confirmada", {"episodio_id": "e1"}) is True

    assert len(falso.mensajes) == 1
    canal, mensaje = falso.mensajes[0]
    assert canal == realtime.CANAL_TRIAGE == "triage:eventos"
    assert json.loads(mensaje)["data"] == {"episodio_id": "e1"}


def test_publicar_sin_redis_url_no_rompe(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert realtime.publicar_evento("x", {}) is False


def test_publicar_con_redis_caido_no_rompe(monkeypatch):
    falso = _ClienteFalso(error=redis.ConnectionError("sin conexión"))
    monkeypatch.setattr(realtime, "_cliente_redis", lambda: falso)
    assert realtime.publicar_evento("x", {}) is False


# --- El endpoint de la decisión publica el evento --------------------------------------


class _CursorFalso:
    """Responde lo mínimo que necesita POST /triage/{id}/decision."""

    def __init__(self, sugerido):
        self.sugerido = sugerido
        self.sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchone(self):
        if "FOR UPDATE" in self.sql:
            return (1,)
        if "clasificacion_ia" in self.sql:
            return None if self.sugerido is None else (self.sugerido,)
        if "INSERT INTO decision_clinica" in self.sql:
            return (FECHA_DECISION,)
        return None  # el episodio aún no tiene decisión


class _ConexionFalsa:
    def __init__(self, sugerido=3):
        self.sugerido = sugerido

    def transaction(self):
        return contextlib.nullcontext()

    def cursor(self):
        return _CursorFalso(self.sugerido)


def _decidir(sugerido=3, **datos):
    app.dependency_overrides[get_conn] = lambda: _ConexionFalsa(sugerido)
    return client.post(f"/api/v1/triage/{uuid.uuid4()}/decision", json=datos)


def _capturar_eventos(monkeypatch):
    eventos = []
    monkeypatch.setattr(
        triage_endpoint, "publicar_evento", lambda tipo, data: eventos.append((tipo, data))
    )
    return eventos


def test_decision_confirmada_publica_un_evento(monkeypatch):
    eventos = _capturar_eventos(monkeypatch)

    r = _decidir(sugerido=3, nivel_esi_final=3)

    assert r.status_code == 201, r.text
    assert len(eventos) == 1
    tipo, data = eventos[0]
    assert tipo == "triage.evaluacion.confirmada"
    assert data["nivel_esi_definitivo"] == 3
    assert data["es_sobrescritura"] is False
    assert data["episodio_id"] == r.json()["episodio_id"]
    assert data["decision_id"] == r.json()["decision_id"]


def test_decision_modificada_marca_es_sobrescritura(monkeypatch):
    eventos = _capturar_eventos(monkeypatch)

    r = _decidir(
        sugerido=3,
        nivel_esi_final=2,
        justificacion="Dificultad respiratoria no captada en triage.",
    )

    assert r.status_code == 201, r.text
    assert eventos[0][1]["es_sobrescritura"] is True
    assert eventos[0][1]["nivel_esi_definitivo"] == 2


def test_el_evento_no_lleva_texto_clinico_ni_datos_personales(monkeypatch):
    eventos = _capturar_eventos(monkeypatch)

    _decidir(sugerido=3, nivel_esi_final=2, justificacion="Dolor torácico con antecedentes.")

    assert set(eventos[0][1]) == {
        "decision_id",
        "episodio_id",
        "usuario_id",
        "nivel_esi_definitivo",
        "es_sobrescritura",
        "fecha_hora_decision",
    }


def test_si_la_decision_falla_no_se_publica_nada(monkeypatch):
    eventos = _capturar_eventos(monkeypatch)

    r = _decidir(sugerido=None, nivel_esi_final=3)  # sin sugerencia de IA: 409

    assert r.status_code == 409
    assert eventos == []


def test_la_decision_responde_201_aunque_redis_este_caido(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # puerto sin Redis

    r = _decidir(sugerido=3, nivel_esi_final=3)

    assert r.status_code == 201, r.text


# --- Integración con el Redis real del docker-compose ----------------------------------


@pytest.mark.skipif(not os.environ.get("REDIS_URL"), reason="requiere REDIS_URL")
def test_un_suscriptor_recibe_el_evento_publicado():
    suscriptor = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    pubsub = suscriptor.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(realtime.CANAL_TRIAGE)
    pubsub.get_message(timeout=2)  # confirmación de la suscripción

    assert realtime.publicar_evento("triage.evaluacion.confirmada", {"episodio_id": "e1"})

    mensaje = None
    for _ in range(10):
        mensaje = pubsub.get_message(timeout=0.5)
        if mensaje:
            break
    pubsub.close()
    suscriptor.close()

    assert mensaje is not None, "el suscriptor no recibió el evento"
    assert json.loads(mensaje["data"])["data"] == {"episodio_id": "e1"}