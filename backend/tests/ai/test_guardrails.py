"""Pruebas de los guardrails del motor de IA (S09-10). Sin internet: el modelo es un falso.

- Cada regla (G1 a G5) por separado.
- El motor descarta la respuesta de la IA que rompe una regla y usa el respaldo.
- Las variables socioeconómicas, geográficas y previsionales no llegan al prompt.
"""
import json
import logging

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from app.ai import engine
from app.ai.contrato import EntradaIA, SalidaIA
from app.ai.guardrails import (
    MARCADOR_OMITIDO,
    redactar_variables_prohibidas,
    tiene_variables_prohibidas,
    validar_salida,
)
from app.ai.reglas import MODELO_RESPALDO

NORMALES = dict(
    presion_sistolica=120, presion_diastolica=80, frecuencia_cardiaca=80,
    frecuencia_respiratoria=16, temperatura=36.6, saturacion_oxigeno=98,
    escala_dolor=0, nivel_conciencia="alerta",
)
JUSTIFICACION = "Los signos vitales y síntomas indican este nivel de urgencia."


def _entrada(motivo=None, **vitales):
    return EntradaIA(
        edad_anios=60, sexo_biologico="masculino",
        signos_vitales={**NORMALES, **vitales}, sintomas=[], motivo_consulta=motivo,
    )


def _salida(nivel, texto=JUSTIFICACION):
    return SalidaIA(nivel_esi=nivel, justificacion=texto)


def _ia(nivel, texto=JUSTIFICACION):
    return RunnableLambda(lambda _p: json.dumps({"nivel_esi": nivel, "justificacion": texto}))


# Un signo crítico cada uno (criterios de ESI 1 del árbol de reglas).
CRITICOS = {
    "spo2_muy_baja": dict(saturacion_oxigeno=82),
    "presion_critica": dict(presion_sistolica=70, presion_diastolica=40),
    "inconsciente": dict(nivel_conciencia="inconsciente"),
    "respuesta_solo_al_dolor": dict(nivel_conciencia="dolor"),
    "bradicardia_extrema": dict(frecuencia_cardiaca=32),
    "fr_muy_baja": dict(frecuencia_respiratoria=6),
}


# --- G1: nivel entero entre 1 y 5 ---------------------------------------------------------


@pytest.mark.parametrize("nivel", [0, 6, -1, 99, True, 2.5, "3", None])
def test_g1_un_nivel_fuera_de_1_a_5_o_que_no_es_entero_se_rechaza(nivel):
    salida = SalidaIA.model_construct(nivel_esi=nivel, justificacion=JUSTIFICACION)
    v = validar_salida(_entrada(), salida)
    assert v is not None and v.regla == "G1_NIVEL_FUERA_DE_RANGO"


@pytest.mark.parametrize("nivel", [0, 6])
def test_g1_el_contrato_tambien_rechaza_niveles_invalidos(nivel):
    with pytest.raises(ValidationError):
        _salida(nivel)


@pytest.mark.parametrize("nivel", [1, 2, 3, 4, 5])
def test_g1_los_niveles_1_a_5_pasan_si_no_hay_criticos(nivel):
    assert validar_salida(_entrada(), _salida(nivel)) is None


# --- G2: justificación no vacía -------------------------------------------------------------


@pytest.mark.parametrize("texto", ["", "   ", "\n\t  "])
def test_g2_una_justificacion_vacia_o_de_espacios_se_rechaza(texto):
    salida = SalidaIA.model_construct(nivel_esi=3, justificacion=texto)
    v = validar_salida(_entrada(), salida)
    assert v is not None and v.regla == "G2_JUSTIFICACION_VACIA"


def test_g2_el_contrato_rechaza_una_justificacion_vacia_o_muy_corta():
    with pytest.raises(ValidationError):
        _salida(3, "")
    with pytest.raises(ValidationError):
        _salida(3, "ok")


# --- G3: signo crítico -> nunca ESI 4 ni 5 ---------------------------------------------------


@pytest.mark.parametrize("nivel", [4, 5])
@pytest.mark.parametrize("critico", CRITICOS.values(), ids=CRITICOS.keys())
def test_g3_con_un_signo_critico_el_esi_4_o_5_se_rechaza(critico, nivel):
    v = validar_salida(_entrada(**critico), _salida(nivel))
    assert v is not None and v.regla == "G3_CRITICO_SUBCLASIFICADO"


@pytest.mark.parametrize("nivel", [1, 2, 3])
@pytest.mark.parametrize("critico", CRITICOS.values(), ids=CRITICOS.keys())
def test_g3_con_un_signo_critico_el_esi_1_a_3_se_acepta(critico, nivel):
    assert validar_salida(_entrada(**critico), _salida(nivel)) is None


def test_g3_sin_signos_criticos_un_esi_5_no_se_bloquea():
    assert validar_salida(_entrada(), _salida(5)) is None


# --- G4: justificación coherente con los signos críticos --------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "Paciente estable, sin alteraciones relevantes.",
        "Los signos vitales normales no justifican urgencia.",
        "Cuadro sin riesgo inmediato para el paciente.",
        "Caso no urgente según la ficha.",
    ],
)
def test_g4_dice_que_esta_estable_con_un_signo_critico_se_rechaza(texto):
    v = validar_salida(_entrada(saturacion_oxigeno=82), _salida(2, texto))
    assert v is not None and v.regla == "G4_JUSTIFICACION_INCOHERENTE"


def test_g4_inestable_no_se_confunde_con_estable():
    texto = "Paciente inestable: saturación de oxígeno críticamente baja."
    assert validar_salida(_entrada(saturacion_oxigeno=82), _salida(1, texto)) is None


def test_g4_sin_signos_criticos_decir_estable_es_valido():
    assert validar_salida(_entrada(), _salida(4, "Paciente estable con un síntoma leve.")) is None


# --- G5: variables socioeconómicas, geográficas y previsionales -------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "Se prioriza menos por ser paciente Fonasa.",
        "Tiene Isapre, por lo que puede esperar.",
        "Dado su nivel socioeconómico bajo, se sube la prioridad.",
        "Vive lejos, en otra comuna, así que conviene atenderlo ya.",
        "Sus ingresos bajos aumentan el riesgo.",
    ],
)
def test_g5_una_justificacion_con_variables_prohibidas_se_rechaza(texto):
    v = validar_salida(_entrada(), _salida(3, texto))
    assert v is not None and v.regla == "G5_VARIABLE_PROHIBIDA"


@pytest.mark.parametrize(
    "texto",
    [
        "Dolor en la región torácica con taquicardia moderada.",
        "Herida en el sector lateral del muslo, sin signos de infección.",
        "Ingreso por dolor abdominal de dos horas de evolución.",
        "Tres ingresos previos por asma, sin hospitalizaciones recientes.",
    ],
)
def test_g5_el_lenguaje_clinico_normal_no_se_bloquea(texto):
    assert validar_salida(_entrada(), _salida(3, texto)) is None


# --- El motor aplica los guardrails ------------------------------------------------------------


@pytest.mark.parametrize("critico", CRITICOS.values(), ids=CRITICOS.keys())
def test_el_motor_descarta_un_esi_5_con_signo_critico_y_usa_el_respaldo(critico):
    r = engine.clasificar(_entrada(**critico), llm=_ia(5))

    assert r.fallback_aplicado is True
    assert r.modelo_usado == MODELO_RESPALDO
    assert r.nivel_esi_sugerido == 1


def test_el_motor_descarta_la_justificacion_incoherente():
    r = engine.clasificar(
        _entrada(saturacion_oxigeno=82), llm=_ia(1, "Paciente estable, sin alteraciones.")
    )
    assert r.fallback_aplicado is True
    assert r.nivel_esi_sugerido == 1


def test_el_motor_descarta_una_justificacion_que_usa_la_prevision():
    r = engine.clasificar(_entrada(), llm=_ia(3, "Por ser paciente Fonasa puede esperar."))
    assert r.fallback_aplicado is True
    assert r.modelo_usado == MODELO_RESPALDO


def test_el_motor_acepta_una_respuesta_correcta_de_la_ia():
    r = engine.clasificar(_entrada(saturacion_oxigeno=82), llm=_ia(1))
    assert r.fallback_aplicado is False
    assert r.nivel_esi_sugerido == 1
    assert r.modelo_usado == engine.MODELO_POR_DEFECTO


def test_el_log_del_guardrail_indica_la_regla_y_no_datos_del_paciente(caplog):
    entrada = _entrada(motivo="Me llamo Ana Pérez, correo ana@correo.cl", saturacion_oxigeno=82)
    with caplog.at_level(logging.WARNING, logger="meditriage.ai"):
        engine.clasificar(entrada, llm=_ia(5))

    registros = [r for r in caplog.records if r.getMessage() == "ia_respaldo_aplicado"]
    assert len(registros) == 1
    assert registros[0].motivo == "Guardrail:G3_CRITICO_SUBCLASIFICADO"
    assert "Ana" not in caplog.text and "ana@correo" not in caplog.text


# --- Variables prohibidas: no llegan al prompt ---------------------------------------------------


def _prompt_completo(entrada) -> str:
    mensajes = engine._PROMPT.format_messages(ficha=engine._ficha(entrada))
    return "\n".join(m.content for m in mensajes)


def test_el_prompt_base_no_nombra_variables_prohibidas():
    assert not tiene_variables_prohibidas(_prompt_completo(_entrada()))


def test_el_texto_del_paciente_sale_sin_prevision_ni_ubicacion():
    motivo = "Soy de Fonasa tramo A, vivo en Puente Alto y tengo dolor de cabeza."
    prompt = _prompt_completo(_entrada(motivo=motivo))

    assert MARCADOR_OMITIDO in prompt
    assert not tiene_variables_prohibidas(prompt)
    for palabra in ("Fonasa", "tramo", "Puente"):
        assert palabra not in prompt
    assert "dolor de cabeza" in prompt


def test_el_texto_clinico_normal_no_se_modifica():
    texto = "Dolor en la región lumbar desde ayer, empeora al caminar."
    assert redactar_variables_prohibidas(texto) == texto


@pytest.mark.parametrize(
    "campo",
    ["prevision", "fonasa_isapre", "comuna", "region", "nivel_socioeconomico", "ingresos",
     "direccion", "rut", "nombre"],
)
def test_el_contrato_rechaza_campos_socioeconomicos_geograficos_o_previsionales(campo):
    datos = dict(edad_anios=40, signos_vitales=NORMALES, sintomas=[], **{campo: "x"})
    with pytest.raises(ValidationError):
        EntradaIA(**datos)


def test_el_hash_de_la_entrada_corresponde_a_la_ficha_que_viaja_a_la_ia():
    import hashlib

    motivo = "Soy de Fonasa y tengo dolor de cabeza."
    entrada = _entrada(motivo=motivo)
    esperado = hashlib.sha256(engine._ficha(entrada).encode("utf-8")).hexdigest()

    assert engine.hash_entrada(entrada) == esperado
    assert engine.hash_entrada(entrada) == engine.hash_entrada(entrada)
    # La ficha ya sale sin la previsión: el hash corresponde a lo que realmente se envió.
    assert "Fonasa" not in engine._ficha(entrada)
