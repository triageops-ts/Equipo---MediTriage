import pytest
from pydantic import ValidationError

from app.schemas.triage import FormularioClinicoInput

PACIENTE = "550e8400-e29b-41d4-a716-446655440000"
SIGNOS_OK = {
    "presion_sistolica": 120,
    "presion_diastolica": 80,
    "frecuencia_cardiaca": 90,
    "frecuencia_respiratoria": 18,
    "temperatura": 37.0,
    "saturacion_oxigeno": 98,
    "escala_dolor": 3,
    "nivel_conciencia": "alerta",
}


def _form(**signos):
    return {"patient_id": PACIENTE, "signos_vitales": {**SIGNOS_OK, **signos}}


def _errores(**signos):
    with pytest.raises(ValidationError) as exc:
        FormularioClinicoInput(**_form(**signos))
    return {e["loc"][-1]: e["msg"] for e in exc.value.errors()}


def test_formulario_valido():
    f = FormularioClinicoInput(**_form())
    assert f.signos_vitales.saturacion_oxigeno == 98
    assert f.usuario_id is None


def test_spo2_150_se_rechaza():
    msg = _errores(saturacion_oxigeno=150)["saturacion_oxigeno"]
    assert "entre 0 y 100" in msg


@pytest.mark.parametrize("campo,valor", [
    ("saturacion_oxigeno", -1),
    ("saturacion_oxigeno", 101),
    ("presion_sistolica", 39),
    ("presion_sistolica", 261),
    ("presion_diastolica", 19),
    ("presion_diastolica", 201),
    ("frecuencia_cardiaca", 19),
    ("frecuencia_cardiaca", 301),
    ("frecuencia_respiratoria", 4),
    ("frecuencia_respiratoria", 81),
    ("temperatura", 29.9),
    ("temperatura", 43.1),
    ("temperatura", -5),
    ("escala_dolor", 11),
    ("escala_dolor", -1),
])
def test_fuera_de_rango(campo, valor):
    assert "rango fisiológico" in _errores(**{campo: valor})[campo]


@pytest.mark.parametrize("campo,valor", [
    ("saturacion_oxigeno", 0), ("saturacion_oxigeno", 100),
    ("presion_sistolica", 260),
    ("frecuencia_cardiaca", 20), ("frecuencia_cardiaca", 300),
    ("temperatura", 30), ("temperatura", 43),
    ("escala_dolor", 0), ("escala_dolor", 10),
])
def test_limites_validos(campo, valor):
    FormularioClinicoInput(**_form(**{campo: valor}))


def test_sistolica_en_el_limite_minimo():
    FormularioClinicoInput(**_form(presion_sistolica=40, presion_diastolica=30))


def test_diastolica_mayor_o_igual_a_sistolica():
    assert "menor que la sistólica" in _errores(presion_sistolica=100, presion_diastolica=100)[
        "presion_diastolica"
    ]


@pytest.mark.parametrize("valor", ["98", 98.5, True, None])
def test_entero_estricto(valor):
    assert "saturacion_oxigeno" in _errores(saturacion_oxigeno=valor)


@pytest.mark.parametrize("valor", [float("nan"), float("inf")])
def test_temperatura_nan_inf(valor):
    assert "temperatura" in _errores(temperatura=valor)


def test_falta_un_signo_vital():
    signos = {k: v for k, v in SIGNOS_OK.items() if k != "frecuencia_cardiaca"}
    with pytest.raises(ValidationError) as exc:
        FormularioClinicoInput(patient_id=PACIENTE, signos_vitales=signos)
    assert exc.value.errors()[0]["type"] == "missing"


def test_nivel_conciencia():
    assert FormularioClinicoInput(**_form(nivel_conciencia=" Alerta ")).signos_vitales.nivel_conciencia == "alerta"
    assert "Debe ser uno de" in _errores(nivel_conciencia="dormido")["nivel_conciencia"]


def test_campo_desconocido_se_rechaza():
    with pytest.raises(ValidationError):
        FormularioClinicoInput(**_form(), paciente="x")


def test_patient_id_invalido():
    with pytest.raises(ValidationError):
        FormularioClinicoInput(patient_id="no-es-uuid", signos_vitales=SIGNOS_OK)


def test_motivo_vacio_queda_en_none():
    f = FormularioClinicoInput(**_form(), motivo_consulta="   ")
    assert f.motivo_consulta is None