from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.patient import PatientInput

BASE = {"rut": "11.111.111-1", "name": "Juan Perez", "has_consent": True}


def _errores(**cambios):
    with pytest.raises(ValidationError) as exc:
        PatientInput(**{**BASE, **cambios})
    return {e["loc"][0]: e["msg"] for e in exc.value.errors()}


def test_valido_y_rut_queda_canonico():
    p = PatientInput(**BASE)
    assert p.rut == "11111111-1"
    assert p.consent_version == "1.0"


def test_rut_con_digito_incorrecto_da_mensaje_claro():
    msg = _errores(rut="11.111.111-2")["rut"]
    assert "dígito verificador" in msg and "se esperaba 1" in msg


def test_rut_mal_formado():
    assert "formato" in _errores(rut="hola")["rut"]


def test_sin_consentimiento_se_rechaza():
    assert "consentimiento" in _errores(has_consent=False)["has_consent"]


def test_version_de_consentimiento_desconocida():
    assert "desconocida" in _errores(consent_version="9.9")["consent_version"]


def test_fecha_futura():
    futura = date.today() + timedelta(days=1)
    assert "futura" in _errores(birth_date=futura)["birth_date"]


def test_email_invalido():
    assert "email" in _errores(email="no-es-un-email")


def test_sexo_invalido():
    assert "biological_sex" in _errores(biological_sex="otro")
