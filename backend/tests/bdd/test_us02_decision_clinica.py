"""Escenario de ejemplo BDD para US-02 usando pytest-bdd y datos sintéticos."""

from pathlib import Path
import pytest
from pytest_bdd import given, parsers, scenario, then, when

from tests.factories import (
    paciente_sintetico,
    signos_vitales_por_esi,
    usuario_por_rol,
)

FEATURE_PATH = Path(__file__).with_name("us02_decision_clinica.feature")


@scenario(str(FEATURE_PATH), "Modificar nivel ESI con justificación válida usando datos sintéticos")
def test_modificar_nivel_esi_us02():
    """Vincula el escenario Gherkin de ejemplo de US-02 con pytest."""


@pytest.fixture
def estado_us02():
    """Guarda los datos sintéticos y el payload de decisión del escenario."""
    return {}


@given(parsers.parse('un usuario con rol "{rol}" y un paciente sintético con consentimiento'))
def dado_usuario_y_paciente(estado_us02, auth_headers, rol):
    estado_us02["usuario"] = usuario_por_rol(rol=rol)
    estado_us02["headers"] = auth_headers(rol)
    estado_us02["paciente"] = paciente_sintetico(name="Ana Soto", has_consent=True)
    estado_us02["signos_vitales"] = signos_vitales_por_esi(3)


@when("se prepara una decisión clínica modificando el nivel ESI sugerido con justificación")
def cuando_prepara_decision(estado_us02):
    estado_us02["nivel_esi_sugerido"] = 3
    estado_us02["decision_payload"] = {
        "nivel_esi_final": 2,
        "justificacion": "Dificultad respiratoria observada en triage.",
    }


@then("la decisión clínica cumple el contrato esperado de US-02")
def entonces_valida_decision(estado_us02):
    payload = estado_us02["decision_payload"]
    assert estado_us02["paciente"]["has_consent"] is True
    assert "Authorization" in estado_us02["headers"]
    assert payload["nivel_esi_final"] != estado_us02["nivel_esi_sugerido"]
    assert len(payload["justificacion"].strip()) >= 10
