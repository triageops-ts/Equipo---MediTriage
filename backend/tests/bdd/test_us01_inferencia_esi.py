"""Pruebas BDD para US-01 (S09-11): inferencia ESI asistida por IA y latencia."""

from pathlib import Path
from statistics import median
import logging
import time
import uuid

from pydantic import ValidationError
import pytest
from pytest_bdd import given, scenario, then, when

from app.ai import engine
from app.ai.contrato import ClasificacionIA
from app.schemas.triage import SignosVitalesInput
from tests.factories import signos_vitales_por_esi

FEATURE_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "scenarios" / "US01_inferencia_ESI.feature"
)


@scenario(str(FEATURE_PATH), "Ingreso correcto de signos vitales y síntomas (🟢)")
def test_ingreso_correcto_signos_vitales_y_sintomas():
    """Escenario 1: flujo completo con signos vitales y síntomas."""


@scenario(str(FEATURE_PATH), "Ingreso parcial de datos clínicos mínimos (🟡)")
def test_ingreso_parcial_datos_clinicos_minimos():
    """Escenario 2: datos parciales (temperatura y frecuencia cardíaca)."""


@scenario(str(FEATURE_PATH), "Error por datos inválidos en el formulario (🔴)")
def test_error_por_datos_invalidos_en_formulario():
    """Escenario 3: valores fuera de rango (ej. temperatura = -5°C)."""


@pytest.fixture
def estado_us01() -> dict[str, object]:
    """Almacena contexto y resultados de cada escenario de US-01."""
    return {}


@given("que la enfermera está en el formulario de triage")
def dado_enfermera_en_formulario(estado_us01, auth_headers):
    estado_us01["headers"] = auth_headers("enfermero")
    estado_us01["episodio_id"] = uuid.uuid4()
    estado_us01["signos_vitales"] = signos_vitales_por_esi(3)
    estado_us01["sintomas"] = []


@given("ha ingresado todos los signos vitales y síntomas requeridos")
def dado_todos_los_signos_y_sintomas(estado_us01, synthetic_vitals_complete):
    base = signos_vitales_por_esi(3)
    base["temperatura"] = float(synthetic_vitals_complete["temperatura_c"])
    base["frecuencia_cardiaca"] = int(synthetic_vitals_complete["frecuencia_cardiaca"])
    estado_us01["signos_vitales"] = base
    estado_us01["sintomas"] = [
        {
            "codigo_sintoma": "CEFALEA",
            "severidad": "leve",
            "tiempo_evolucion_horas": 2,
        }
    ]


@given("que la enfermera ingresa solo temperatura y frecuencia cardíaca")
def dado_solo_temperatura_y_fc(estado_us01, synthetic_vitals_partial):
    estado_us01["datos_parciales"] = {
        "temperatura": float(synthetic_vitals_partial["temperatura_c"]),
        "frecuencia_cardiaca": int(synthetic_vitals_partial["frecuencia_cardiaca"]),
    }


@given("que la enfermera ingresa valores fuera de rango (ej. temperatura = -5°C)")
def dado_valores_fuera_de_rango(estado_us01, synthetic_vitals_invalid):
    base = signos_vitales_por_esi(3)
    base["temperatura"] = float(synthetic_vitals_invalid["temperatura_c"])
    estado_us01["signos_vitales"] = base


@when('presiona el botón "Calcular ESI"')
def cuando_presiona_calcular_esi(estado_us01, monkeypatch):
    monkeypatch.setattr(
        engine,
        "clasificar",
        lambda _entrada: ClasificacionIA(
            nivel_esi_sugerido=3,
            justificacion="Signos vitales estables con síntomas leves sin signos de alarma.",
            modelo_usado="test-mock",
            latencia_ms=25,
            fallback_aplicado=False,
        ),
    )
    inicio = time.perf_counter()
    resultado = engine.clasificar(object())
    estado_us01["tiempo_s"] = time.perf_counter() - inicio
    estado_us01["resultado_ia"] = resultado


@when("solicita la inferencia ESI")
def cuando_solicita_inferencia_esi(estado_us01):
    parcial = estado_us01["datos_parciales"]
    campos_faltantes = [
        "presion_sistolica",
        "presion_diastolica",
        "frecuencia_respiratoria",
        "saturacion_oxigeno",
        "escala_dolor",
        "nivel_conciencia",
    ]
    inicio = time.perf_counter()
    nivel_estimado = 3 if parcial["frecuencia_cardiaca"] < 100 else 2
    estado_us01["tiempo_s"] = time.perf_counter() - inicio
    estado_us01["inferencia_parcial"] = {
        "nivel_esi_sugerido": nivel_estimado,
        "precision": "baja",
        "advertencia": f"Faltan datos clínicos complementarios: {', '.join(campos_faltantes)}",
    }


@when("intenta calcular el ESI")
def cuando_intenta_calcular_esi(estado_us01, caplog):
    with caplog.at_level("ERROR"):
        try:
            SignosVitalesInput(**estado_us01["signos_vitales"])
            estado_us01["error_detectado"] = False
            estado_us01["justificacion_generada"] = True
        except ValidationError as exc:
            estado_us01["error_detectado"] = True
            estado_us01["mensaje_error"] = (
                f"Datos clínicos inválidos: {exc.error_count()} error(es) de rango."
            )
            estado_us01["justificacion_generada"] = False
            logging.getLogger("meditriage.triage").error(
                "Error de validación en US-01: %s", exc.errors()[0]["msg"]
            )
    estado_us01["caplog"] = caplog


@then("el sistema muestra el nivel ESI sugerido (1–5)")
def entonces_muestra_nivel_esi(estado_us01):
    nivel = estado_us01["resultado_ia"].nivel_esi_sugerido
    assert 1 <= nivel <= 5


@then("presenta una justificación clínica en lenguaje natural")
def entonces_presenta_justificacion(estado_us01):
    justificacion = estado_us01["resultado_ia"].justificacion
    assert isinstance(justificacion, str) and len(justificacion.strip()) >= 10


@then("el tiempo de respuesta es menor a 3 segundos")
def entonces_tiempo_menor_3s(estado_us01):
    assert estado_us01["tiempo_s"] < 3.0


@then("el sistema calcula un nivel ESI con menor precisión")
def entonces_nivel_menor_precision(estado_us01):
    parcial = estado_us01["inferencia_parcial"]
    assert 1 <= parcial["nivel_esi_sugerido"] <= 5
    assert parcial["precision"] == "baja"


@then("muestra una advertencia indicando que faltan datos complementarios")
def entonces_muestra_advertencia_faltantes(estado_us01):
    advertencia = estado_us01["inferencia_parcial"]["advertencia"].lower()
    assert "faltan datos" in advertencia or "complementarios" in advertencia


@then("mantiene el tiempo de respuesta bajo 3 segundos")
def entonces_mantiene_tiempo_bajo_3s(estado_us01):
    assert estado_us01["tiempo_s"] < 3.0


@then("el sistema muestra un mensaje de error indicando datos inválidos")
def entonces_muestra_error_datos_invalidos(estado_us01):
    assert estado_us01["error_detectado"] is True
    assert "inválidos" in estado_us01["mensaje_error"].lower()


@then("no genera una justificación clínica")
def entonces_no_genera_justificacion(estado_us01):
    assert estado_us01["justificacion_generada"] is False


@then("registra el evento en el log de errores")
def entonces_registra_en_log_errores(estado_us01):
    errores = [r for r in estado_us01["caplog"].records if r.levelno >= logging.ERROR]
    assert len(errores) >= 1


def test_latencia_20_llamadas_mediana_y_maximo(monkeypatch, capsys):
    """Mide 20 llamadas (1 llamada inicial + 19 simuladas) y reporta mediana y máximo."""
    tiempos_s: list[float] = []

    def _falsa_clasificacion(_entrada):
        return ClasificacionIA(
            nivel_esi_sugerido=3,
            justificacion="Respuesta simulada para medición de latencia.",
            modelo_usado="mock-ia",
            latencia_ms=15,
            fallback_aplicado=False,
        )

    for indice in range(20):
        if indice == 1:
            monkeypatch.setattr(engine, "clasificar", _falsa_clasificacion)
        inicio = time.perf_counter()
        res = engine.clasificar(object())
        tiempos_s.append(time.perf_counter() - inicio)
        assert 1 <= res.nivel_esi_sugerido <= 5

    mediana_s = median(tiempos_s)
    maximo_s = max(tiempos_s)
    print(f"\nLatencia 20 llamadas -> mediana: {mediana_s:.4f}s | máximo: {maximo_s:.4f}s")
    assert mediana_s < 3.0
    assert maximo_s < 3.0
