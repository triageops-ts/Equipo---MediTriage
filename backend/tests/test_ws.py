"""Pruebas del canal WebSocket del tablero (/api/v1/ws/tablero).

- Sin REDIS_URL se prueba solo que el canal avisa (cierre 1011) cuando Redis no está.
- Con REDIS_URL (el Redis real del docker-compose) se prueba el recorrido completo:
  evento publicado -> Redis -> WebSocket -> cliente. Se omiten si no hay REDIS_URL.
"""
import contextlib
import os
import threading
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core import realtime
from app.db import get_conn
from app.main import app

client = TestClient(app)
URL_WS = "/api/v1/ws/tablero"

requiere_redis = pytest.mark.skipif(
    not os.environ.get("REDIS_URL"), reason="requiere REDIS_URL"
)


@pytest.fixture(autouse=True)
def _limpiar(monkeypatch):
    monkeypatch.setattr(realtime, "_cliente", None)
    yield
    app.dependency_overrides.clear()


@contextlib.contextmanager
def _limite(ws, segundos=10):
    """Si no llega nada en `segundos`, cierra el socket para que la prueba falle y no se cuelgue."""
    reloj = threading.Timer(segundos, ws.close)
    reloj.start()
    try:
        yield
    finally:
        reloj.cancel()


def _recibir(ws):
    with _limite(ws):
        return ws.receive_json()


# --- Sin Redis ---------------------------------------------------------------------------


def test_sin_redis_url_el_canal_cierra_con_1011(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)

    with client.websocket_connect(URL_WS) as ws:
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()

    assert error.value.code == 1011


def test_con_redis_caido_el_canal_cierra_con_1011(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # puerto sin Redis

    with client.websocket_connect(URL_WS) as ws:
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()

    assert error.value.code == 1011


# --- Con el Redis real -------------------------------------------------------------------


@requiere_redis
def test_al_conectar_avisa_que_el_canal_esta_listo():
    with client.websocket_connect(URL_WS) as ws:
        aviso = _recibir(ws)

    assert aviso == {"event_type": "conexion.lista", "canal": "triage:eventos"}


@requiere_redis
def test_el_cliente_recibe_el_evento_publicado():
    with client.websocket_connect(URL_WS) as ws:
        assert _recibir(ws)["event_type"] == "conexion.lista"

        assert realtime.publicar_evento("triage.evaluacion.confirmada", {"episodio_id": "e1"})
        evento = _recibir(ws)

    assert evento["event_type"] == "triage.evaluacion.confirmada"
    assert evento["data"] == {"episodio_id": "e1"}


@requiere_redis
def test_varios_tableros_reciben_el_mismo_evento():
    with client.websocket_connect(URL_WS) as ws1, client.websocket_connect(URL_WS) as ws2:
        assert _recibir(ws1)["event_type"] == "conexion.lista"
        assert _recibir(ws2)["event_type"] == "conexion.lista"

        realtime.publicar_evento("triage.evaluacion.confirmada", {"episodio_id": "e2"})

        assert _recibir(ws1)["data"] == {"episodio_id": "e2"}
        assert _recibir(ws2)["data"] == {"episodio_id": "e2"}


@requiere_redis
def test_lo_que_envia_el_cliente_se_ignora_y_el_canal_sigue_vivo():
    with client.websocket_connect(URL_WS) as ws:
        assert _recibir(ws)["event_type"] == "conexion.lista"

        ws.send_text("hola")
        realtime.publicar_evento("triage.evaluacion.confirmada", {"episodio_id": "e3"})

        assert _recibir(ws)["data"] == {"episodio_id": "e3"}


# --- Recorrido completo: registrar la decisión -> el tablero lo recibe ---------------------


class _CursorFalso:
    """Responde lo mínimo que necesita POST /triage/{id}/decision."""

    def __init__(self):
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
            return (3,)  # la IA sugirió ESI 3
        if "INSERT INTO decision_clinica" in self.sql:
            return (datetime(2026, 11, 13, 20, 0, 0),)
        return None


class _ConexionFalsa:
    def transaction(self):
        return contextlib.nullcontext()

    def cursor(self):
        return _CursorFalso()


@requiere_redis
def test_al_registrar_la_decision_el_tablero_recibe_el_evento():
    app.dependency_overrides[get_conn] = lambda: _ConexionFalsa()
    episodio_id = str(uuid.uuid4())

    with client.websocket_connect(URL_WS) as ws:
        assert _recibir(ws)["event_type"] == "conexion.lista"

        r = client.post(
            f"/api/v1/triage/{episodio_id}/decision",
            json={
                "nivel_esi_final": 2,
                "justificacion": "Dificultad respiratoria no captada en triage.",
            },
        )
        assert r.status_code == 201, r.text

        evento = _recibir(ws)

    assert evento["event_type"] == "triage.evaluacion.confirmada"
    assert evento["data"]["episodio_id"] == episodio_id
    assert evento["data"]["nivel_esi_definitivo"] == 2
    assert evento["data"]["es_sobrescritura"] is True
    assert "justificacion" not in evento["data"]