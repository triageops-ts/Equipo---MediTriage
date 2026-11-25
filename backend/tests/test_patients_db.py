"""Pruebas de POST /patients contra una base real.

Se omiten si no hay DATABASE_URL (levantar con `docker compose up db` y aplicar
init.sql). Requiere además APP_ENCRYPTION_KEY.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import crear_token
from app.main import app

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)

# Los endpoints exigen sesión: se firma un token de enfermero (no consulta la base).
_TOKEN = crear_token(uuid.uuid4(), "enfermero")[0]
client = TestClient(app, headers={"Authorization": f"Bearer {_TOKEN}"})


def _rut_unico() -> str:
    from app.core.rut import calcular_dv, formatear_rut

    cuerpo = str(10_000_000 + uuid.uuid4().int % 80_000_000)
    return formatear_rut(f"{cuerpo}-{calcular_dv(cuerpo)}")


def test_crea_paciente_y_consentimiento():
    rut = _rut_unico()
    r = client.post("/api/v1/patients", json={"rut": rut, "name": "Ana Soto", "has_consent": True})
    assert r.status_code == 201
    body = r.json()
    assert body["rut"] == rut
    assert body["consent_version"] == "1.0"
    assert body["consent_accepted_at"]


def test_rut_duplicado_409():
    rut = _rut_unico()
    datos = {"rut": rut, "name": "Ana Soto", "has_consent": True}
    assert client.post("/api/v1/patients", json=datos).status_code == 201
    r = client.post("/api/v1/patients", json=datos)
    assert r.status_code == 409
    assert rut in r.json()["detail"]


def test_rut_invalido_422_con_mensaje():
    r = client.post(
        "/api/v1/patients", json={"rut": "11.111.111-2", "name": "Ana Soto", "has_consent": True}
    )
    assert r.status_code == 422
    err = r.json()["errors"][0]
    assert err["field"] == "rut" and "dígito verificador" in err["message"]


def test_buscar_por_rut():
    rut = _rut_unico()
    client.post("/api/v1/patients", json={"rut": rut, "name": "Ana Soto", "has_consent": True})
    r = client.get("/api/v1/patients", params={"rut": rut})
    assert r.status_code == 200
    assert r.json()[0]["name"] == "Ana Soto"
    assert r.json()[0]["rut"] == rut


def test_buscar_rut_inexistente_devuelve_lista_vacia():
    r = client.get("/api/v1/patients", params={"rut": _rut_unico()})
    assert r.status_code == 200
    assert r.json() == []


def test_buscar_rut_invalido_422():
    r = client.get("/api/v1/patients", params={"rut": "11.111.111-2"})
    assert r.status_code == 422


# --- PATCH /patients/{patient_id} ---


def _crear(nombre: str = "Ana Soto", **extra) -> tuple[str, str]:
    rut = _rut_unico()
    r = client.post(
        "/api/v1/patients", json={"rut": rut, "name": nombre, "has_consent": True, **extra}
    )
    assert r.status_code == 201, r.text
    return r.json()["patient_id"], rut


def test_editar_nombre_fecha_y_sexo():
    patient_id, rut = _crear()
    r = client.patch(
        f"/api/v1/patients/{patient_id}",
        json={"name": "Ana María Soto", "birth_date": "1985-04-12", "biological_sex": "female"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "patient_id": patient_id,
        "rut": rut,
        "name": "Ana María Soto",
        "birth_date": "1985-04-12",
        "biological_sex": "female",
    }
    # La búsqueda por RUT ya devuelve los datos nuevos.
    encontrado = client.get("/api/v1/patients", params={"rut": rut}).json()[0]
    assert encontrado["name"] == "Ana María Soto"
    assert encontrado["birth_date"] == "1985-04-12"


def test_editar_solo_un_campo_no_toca_los_demas():
    patient_id, _ = _crear(birth_date="1990-01-01", biological_sex="male")
    r = client.patch(f"/api/v1/patients/{patient_id}", json={"name": "Ana Soto Rojas"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Ana Soto Rojas"
    assert body["birth_date"] == "1990-01-01"
    assert body["biological_sex"] == "male"


def test_editar_puede_vaciar_la_fecha():
    patient_id, _ = _crear(birth_date="1990-01-01")
    r = client.patch(f"/api/v1/patients/{patient_id}", json={"birth_date": None})
    assert r.status_code == 200, r.text
    assert r.json()["birth_date"] is None


def test_editar_paciente_inexistente_404():
    r = client.patch(f"/api/v1/patients/{uuid.uuid4()}", json={"name": "Ana Soto"})
    assert r.status_code == 404


def test_editar_sin_campos_422():
    patient_id, _ = _crear()
    assert client.patch(f"/api/v1/patients/{patient_id}", json={}).status_code == 422


def test_editar_rut_no_se_permite_422():
    patient_id, rut = _crear()
    r = client.patch(f"/api/v1/patients/{patient_id}", json={"rut": _rut_unico()})
    assert r.status_code == 422
    # El RUT sigue siendo el original.
    assert client.get("/api/v1/patients", params={"rut": rut}).json()[0]["patient_id"] == patient_id


def test_editar_con_rol_medico_403():
    patient_id, _ = _crear()
    token_medico = crear_token(uuid.uuid4(), "medico")[0]
    r = client.patch(
        f"/api/v1/patients/{patient_id}",
        json={"name": "Otro Nombre"},
        headers={"Authorization": f"Bearer {token_medico}"},
    )
    assert r.status_code == 403


def test_editar_sin_sesion_401():
    anonimo = TestClient(app)
    r = anonimo.patch(f"/api/v1/patients/{uuid.uuid4()}", json={"name": "Ana Soto"})
    assert r.status_code == 401
