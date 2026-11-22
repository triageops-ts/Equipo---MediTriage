"""GET /audit-logs y /audit-logs/verificacion contra Postgres real (S10-6, US-05).

Se omite sin DATABASE_URL y APP_ENCRYPTION_KEY. Usa el flujo completo de test_auditoria_db
(evaluar + decidir) para generar registros reales. Solo escribe lo que ya escribe ese flujo:
la prueba de cadena rota altera un registro DENTRO de una transacción que se deshace,
así que no deja nada alterado en la base.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.audit_logs import _PRIMER_ROTO
from app.core.security import crear_token
from app.main import app
from test_auditoria_db import _admin, _flujo_completo

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)

client = TestClient(app)
MOTIVO = "Dificultad respiratoria no captada en triage."


def _cabecera(rol):
    token, _ = crear_token(uuid.uuid4(), rol)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _sin_clave_de_ia(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _flujo_con_final():
    # El nivel sugerido se conoce después de evaluar: primero se prueba con 5 y, si la IA
    # sugirió 5, el flujo se repite con 4.
    ep, sugerido, _ = _flujo_completo(nivel_final=5, justificacion=MOTIVO)
    if sugerido == 5:
        ep, sugerido, _ = _flujo_completo(nivel_final=4, justificacion=MOTIVO)
    return ep, sugerido


def _listar(**params):
    r = client.get("/api/v1/audit-logs", params=params, headers=_cabecera("auditor"))
    assert r.status_code == 200, r.text
    return r.json()


def test_auditor_ve_sugerencia_decision_y_marca_de_modificacion():
    ep, sugerido = _flujo_con_final()
    decision, ia = _listar(episodio_id=ep)  # del más reciente al más antiguo
    assert decision["evento_tipo"] == "triage.override.ejecutado"
    assert decision["hay_discrepancia"] is True
    assert decision["sugerencia_ia"] == sugerido
    assert decision["decision_final"] not in (None, sugerido)
    assert ia["hay_discrepancia"] is False
    assert ia["sugerencia_ia"] == sugerido and ia["decision_final"] is None
    assert ia["prompt_enviado"]  # el prompt registrado viaja en la respuesta
    assert decision["hash_anterior"] == ia["hash_actual"]  # la cadena se ve en la respuesta


def test_filtro_hay_discrepancia():
    ep, _ = _flujo_con_final()
    solo_si = _listar(episodio_id=ep, hay_discrepancia=True)
    solo_no = _listar(episodio_id=ep, hay_discrepancia=False)
    assert [x["evento_tipo"] for x in solo_si] == ["triage.override.ejecutado"]
    assert len(solo_no) == 1 and solo_no[0]["hay_discrepancia"] is False


def test_filtro_por_usuario_y_paginacion():
    ep, _ = _flujo_con_final()
    todos = _listar(episodio_id=ep)
    actor = todos[0]["usuario_id_actor"]
    de_actor = _listar(usuario_id=actor, limit=100)
    assert {x["registro_id"] for x in todos} <= {x["registro_id"] for x in de_actor}
    assert all(x["usuario_id_actor"] == actor for x in de_actor)

    primero = _listar(episodio_id=ep, limit=1, skip=0)
    segundo = _listar(episodio_id=ep, limit=1, skip=1)
    assert len(primero) == len(segundo) == 1
    assert primero[0]["registro_id"] == todos[0]["registro_id"]
    assert segundo[0]["registro_id"] == todos[1]["registro_id"]
    assert _listar(episodio_id=ep, skip=2) == []


@pytest.mark.parametrize("rol", ["enfermero", "medico"])
def test_otros_roles_no_ven_la_auditoria(rol):
    for ruta in ("/api/v1/audit-logs", "/api/v1/audit-logs/verificacion"):
        assert client.get(ruta, headers=_cabecera(rol)).status_code == 403


def test_verificacion_cadena_valida():
    _flujo_con_final()
    r = client.get("/api/v1/audit-logs/verificacion", headers=_cabecera("auditor"))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["valida"] is True and cuerpo["primer_registro_alterado"] is None
    assert cuerpo["registros_verificados"] >= 2


def test_primer_registro_alterado_se_detecta_y_no_queda_nada_alterado():
    ep, _ = _flujo_con_final()
    decision, ia = _listar(episodio_id=ep)
    conn = _admin()
    try:
        # Solo el dueño puede desactivar los triggers, y solo dentro de esta transacción.
        conn.execute("ALTER TABLE registro_auditoria DISABLE TRIGGER USER")
        conn.execute(
            "UPDATE registro_auditoria SET sugerencia_ia = 1 WHERE registro_id = %s",
            (ia["registro_id"],),
        )
        primero = conn.execute(_PRIMER_ROTO).fetchone()
        assert str(primero[0]) == ia["registro_id"]
        assert "hash_actual" in primero[1]
    finally:
        conn.rollback()  # deshace el UPDATE y reactiva los triggers
        conn.close()
    r = client.get("/api/v1/audit-logs/verificacion", headers=_cabecera("auditor"))
    assert r.json()["valida"] is True
