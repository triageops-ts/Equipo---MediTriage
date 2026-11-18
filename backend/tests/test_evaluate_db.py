"""POST /triage/{id}/evaluate contra una base real (S09-7).

Se omite sin DATABASE_URL y APP_ENCRYPTION_KEY. Sin ANTHROPIC_API_KEY el motor usa el
árbol de reglas, así que estas pruebas no llaman a internet y el resultado es determinista.
"""
import os
import uuid

import psycopg
import pytest

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


def _filas(episodio_id: str):
    with _admin() as conn:
        return conn.execute(
            "SELECT nivel_esi_sugerido, modelo_usado, fallback_aplicado, hash_datos_enviados_ia, "
            "tiempo_respuesta >= tiempo_solicitud FROM clasificacion_ia WHERE episodio_id = %s",
            (episodio_id,),
        ).fetchall()


def _ponerle_fecha_de_nacimiento(episodio_id: str):
    with _admin() as conn:
        conn.execute(
            "UPDATE paciente SET fecha_nacimiento = '1980-01-01' WHERE paciente_id = "
            "(SELECT paciente_id FROM episodio_triage WHERE episodio_id = %s)",
            (episodio_id,),
        )


def test_sin_ia_se_guarda_el_respaldo_y_luego_se_puede_decidir():
    ep = _episodio(sugerido=None)
    _ponerle_fecha_de_nacimiento(ep)
    r = _post(f"/api/v1/triage/{ep}/evaluate")
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["fallback_aplicado"] is True and b["modelo_usado"] == "fallback-rule-engine"
    (fila,) = _filas(ep)
    assert fila[0] == b["nivel_esi_sugerido"] and fila[2] is True
    assert len(fila[3]) == 64 and fila[4] is True

    # La sugerencia guardada habilita POST /decision (antes respondía siempre 409).
    d = _post(f"/api/v1/triage/{ep}/decision", json={"nivel_esi_final": b["nivel_esi_sugerido"]})
    assert d.status_code == 201, d.text


def test_idempotency_key_no_duplica_filas():
    ep = _episodio(sugerido=None)
    _ponerle_fecha_de_nacimiento(ep)
    cab = {**_cabecera_enfermero(), "Idempotency-Key": str(uuid.uuid4())}
    a = _post(f"/api/v1/triage/{ep}/evaluate", headers=cab)
    b = _post(f"/api/v1/triage/{ep}/evaluate", headers=cab)
    assert a.status_code == b.status_code == 201
    assert a.json() == b.json()
    assert len(_filas(ep)) == 1


def test_episodio_inexistente_404():
    assert _post(f"/api/v1/triage/{uuid.uuid4()}/evaluate").status_code == 404
