import pytest
from pydantic import ValidationError

from app.schemas.decision import DecisionInput


def test_confirmacion_sin_justificacion_es_valida():
    d = DecisionInput(nivel_esi_final=3)
    assert d.nivel_esi_final == 3 and d.justificacion is None


@pytest.mark.parametrize("nivel", [0, 6, -1, 10])
def test_nivel_fuera_de_rango_se_rechaza(nivel):
    with pytest.raises(ValidationError) as e:
        DecisionInput(nivel_esi_final=nivel)
    assert "entre 1 y 5" in str(e.value)


@pytest.mark.parametrize("nivel", ["3", 3.0, True, None])
def test_nivel_debe_ser_entero_estricto(nivel):
    with pytest.raises(ValidationError):
        DecisionInput(nivel_esi_final=nivel)


def test_justificacion_se_limpia_y_vacia_queda_en_none():
    assert DecisionInput(nivel_esi_final=2, justificacion="  dolor   intenso  ").justificacion == "dolor intenso"
    assert DecisionInput(nivel_esi_final=2, justificacion="   ").justificacion is None


def test_campos_extra_se_rechazan():
    with pytest.raises(ValidationError):
        DecisionInput(nivel_esi_final=2, modificado_manualmente=True)