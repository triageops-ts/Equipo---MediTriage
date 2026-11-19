"""Auditoría inmutable contra Postgres real (S10-4, US-05).

Se omite sin DATABASE_URL y APP_ENCRYPTION_KEY. Las lecturas de verificación usan
MIGRATION_DATABASE_URL (dueño); los intentos de UPDATE/DELETE se hacen como meditriage_app.
"""
import os
import uuid

import psycopg
import pytest
from psycopg import errors

from app.db import set_rls_context
from test_decision_db import _cabecera_enfermero, _episodio, _post

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)


@pytest.fixture(autouse=True)
def _sin_clave_de_ia(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _admin():
    return psycopg.connect(os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"])


def _registros(episodio_id):
    with _admin() as conn:
        return conn.execute(
            """SELECT evento_tipo, sugerencia_ia, decision_final, hay_discrepancia,
                      prompt_enviado, hash_anterior, hash_actual, registro_id
               FROM registro_auditoria WHERE episodio_id = %s
               ORDER BY fecha_hora_evento, registro_id""",
            (episodio_id,),
        ).fetchall()


def _con_nacimiento(ep):
    with _admin() as conn:
        conn.execute(
            "UPDATE paciente SET fecha_nacimiento = '1980-01-01' WHERE paciente_id = "
            "(SELECT paciente_id FROM episodio_triage WHERE episodio_id = %s)",
            (ep,),
        )


def _flujo_completo(nivel_final=None, justificacion=None):
    ep = _episodio(sugerido=None)
    _con_nacimiento(ep)
    ev = _post(f"/api/v1/triage/{ep}/evaluate")
    assert ev.status_code == 201, ev.text
    sugerido = ev.json()["nivel_esi_sugerido"]
    body = {"nivel_esi_final": nivel_final or sugerido}
    if justificacion:
        body["justificacion"] = justificacion
    d = _post(f"/api/v1/triage/{ep}/decision", json=body)
    assert d.status_code == 201, d.text
    return ep, sugerido, d.json()


def test_evaluate_y_decision_escriben_auditoria_con_cadena():
    ep, sugerido, _ = _flujo_completo()
    ia, dec = _registros(ep)
    assert ia[0] in ("ia.clasificacion.sugerida", "triage.clasificacion.respaldo_aplicada")
    assert ia[1] == sugerido and ia[4] and "Edad:" in ia[4]  # prompt sanitizado guardado
    assert dec[0] == "triage.evaluacion.confirmada"
    assert dec[1] == dec[2] == sugerido and dec[3] is False
    assert dec[5] == ia[6]  # hash_anterior de uno = hash_actual del anterior
    assert len(dec[6]) == 64


def test_decision_distinta_guarda_ambas_y_discrepancia():
    ep = _episodio(sugerido=None)
    _con_nacimiento(ep)
    sug = _post(f"/api/v1/triage/{ep}/evaluate").json()["nivel_esi_sugerido"]
    final = 5 if sug != 5 else 4
    d = _post(
        f"/api/v1/triage/{ep}/decision",
        json={"nivel_esi_final": final, "justificacion": "Criterio clínico de la enfermera tratante"},
    )
    assert d.status_code == 201, d.text
    dec = _registros(ep)[-1]
    assert dec[0] == "triage.override.ejecutado"
    assert (dec[1], dec[2], dec[3]) == (sug, final, True)


def test_cadena_integra():
    _flujo_completo()
    with _admin() as conn:
        assert conn.execute("SELECT * FROM verificar_cadena_auditoria()").fetchall() == []


def test_app_no_puede_update_ni_delete_ni_truncate():
    ep, _, _ = _flujo_completo()
    rid = _registros(ep)[0][7]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        usuario = conn.execute("SELECT usuario_id FROM usuario_staff WHERE rol='enfermero' LIMIT 1")
        # permisos: sin UPDATE/DELETE para meditriage_app
        conn.rollback()
        set_rls_context(conn, "enfermero", uuid.uuid4())
        for sql in (
            "UPDATE registro_auditoria SET decision_final = 1 WHERE registro_id = %s",
            "DELETE FROM registro_auditoria WHERE registro_id = %s",
        ):
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(sql, (rid,))
            conn.rollback()
            set_rls_context(conn, "enfermero", uuid.uuid4())
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("TRUNCATE registro_auditoria")


def test_trigger_bloquea_incluso_al_dueno():
    ep, _, _ = _flujo_completo()
    rid = _registros(ep)[0][7]
    for sql in (
        "UPDATE registro_auditoria SET decision_final = 1 WHERE registro_id = %s",
        "DELETE FROM registro_auditoria WHERE registro_id = %s",
    ):
        with _admin() as conn:
            with pytest.raises(errors.InsufficientPrivilege, match="append-only"):
                conn.execute(sql, (rid,))
    with _admin() as conn:
        with pytest.raises(errors.InsufficientPrivilege, match="append-only"):
            conn.execute("TRUNCATE registro_auditoria")
    assert len(_registros(ep)) == 2  # siguen intactos


def test_hash_enviado_por_el_cliente_se_ignora():
    ep = _episodio(sugerido=3)
    with _admin() as conn:
        uid = conn.execute("SELECT usuario_id FROM usuario_staff WHERE rol='enfermero' LIMIT 1").fetchone()[0]
        conn.execute(
            """INSERT INTO registro_auditoria
               (registro_id, episodio_id, evento_tipo, usuario_id_actor, hay_discrepancia,
                hash_anterior, hash_actual)
               VALUES (%s, %s, 'prueba', %s, false, 'x', 'y')""",
            (uuid.uuid4(), ep, uid),
        )
        assert conn.execute("SELECT * FROM verificar_cadena_auditoria()").fetchall() == []


def test_si_falla_el_log_se_revierte_la_decision(monkeypatch):
    """Escenario 🔴 de US-05: sin auditoría no hay hecho clínico."""
    from app import audit

    ep = _episodio(sugerido=3)
    original = audit._INSERT
    monkeypatch.setattr(audit, "_INSERT", original.replace("registro_auditoria", "tabla_que_no_existe", 1))
    from fastapi.testclient import TestClient
    from app.main import app

    r = TestClient(app, raise_server_exceptions=False).post(
        f"/api/v1/triage/{ep}/decision",
        json={"nivel_esi_final": 3},
        headers=_cabecera_enfermero(),
    )
    assert r.status_code == 500
    with _admin() as conn:
        n = conn.execute("SELECT count(*) FROM decision_clinica WHERE episodio_id = %s", (ep,)).fetchone()[0]
    assert n == 0
