"""Pruebas del motor de IA (S09-4). No llaman a internet: el modelo es siempre un falso.

- 5 casos sintéticos, uno por nivel ESI, con la IA respondiendo bien.
- El árbol de reglas de respaldo por separado, también un caso por nivel.
- IA que falla, tarda más de 1500 ms o devuelve algo inválido -> reglas + fallback_aplicado.
- Aislamiento (Factor 06): dos llamadas seguidas no comparten datos.
- Contrato: un campo prohibido (RUT, nombre...) se rechaza.
"""
import json
import time

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from app.ai import engine
from app.ai.contrato import EntradaIA
from app.ai.reglas import MODELO_RESPALDO, clasificar_por_reglas

NORMALES = dict(
    presion_sistolica=120,
    presion_diastolica=80,
    frecuencia_cardiaca=80,
    frecuencia_respiratoria=16,
    temperatura=36.6,
    saturacion_oxigeno=98,
    escala_dolor=0,
    nivel_conciencia="alerta",
)


def _entrada(*, edad=40, sexo="femenino", sintomas=(), motivo=None, **vitales):
    return EntradaIA(
        edad_anios=edad,
        sexo_biologico=sexo,
        signos_vitales={**NORMALES, **vitales},
        sintomas=[
            {"codigo_sintoma": c, "severidad": sev, "tiempo_evolucion_horas": 2}
            for c, sev in sintomas
        ],
        motivo_consulta=motivo,
    )


# Un caso por nivel ESI: (entrada, nivel esperado)
CASOS = {
    1: _entrada(
        nivel_conciencia="inconsciente", saturacion_oxigeno=82, presion_sistolica=70,
        presion_diastolica=40,
    ),
    2: _entrada(
        saturacion_oxigeno=92, frecuencia_cardiaca=120, escala_dolor=9,
        sintomas=[("dolor_toracico", "severa")],
    ),
    3: _entrada(
        frecuencia_cardiaca=105, temperatura=38.2, escala_dolor=5,
        sintomas=[("tos", "moderada"), ("fiebre", "moderada")],
    ),
    4: _entrada(escala_dolor=2, sintomas=[("esguince_tobillo", "leve")]),
    5: _entrada(),
}


def _ia_responde(nivel, texto="Taquicardia y desaturación leve sugieren urgencia."):
    """Modelo falso que responde el JSON que pide el contrato."""
    return RunnableLambda(lambda _prompt: json.dumps({"nivel_esi": nivel, "justificacion": texto}))


@pytest.fixture(autouse=True)
def _sin_internet(monkeypatch):
    """Ninguna prueba puede crear un cliente real de Anthropic."""
    def _prohibido(*args, **kwargs):
        raise AssertionError("la prueba intentó crear un cliente real de Anthropic")

    monkeypatch.setattr(engine, "_cliente_anthropic", _prohibido)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)


# --- IA responde bien: un caso por nivel ESI --------------------------------------------


@pytest.mark.parametrize("nivel", [1, 2, 3, 4, 5])
def test_ia_responde_y_se_devuelve_su_nivel(nivel):
    r = engine.clasificar(CASOS[nivel], llm=_ia_responde(nivel))

    assert r.nivel_esi_sugerido == nivel
    assert r.fallback_aplicado is False
    assert r.modelo_usado == engine.MODELO_POR_DEFECTO
    assert r.justificacion
    assert r.latencia_ms >= 0


def test_el_modelo_se_puede_cambiar_por_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "modelo-de-prueba")
    r = engine.clasificar(CASOS[3], llm=_ia_responde(3))
    assert r.modelo_usado == "modelo-de-prueba"


def test_acepta_el_json_dentro_de_un_bloque_de_codigo():
    texto = '```json\n{"nivel_esi": 2, "justificacion": "Dolor torácico con taquicardia."}\n```'
    r = engine.clasificar(CASOS[2], llm=RunnableLambda(lambda _p: texto))
    assert r.nivel_esi_sugerido == 2 and r.fallback_aplicado is False


# --- Árbol de reglas: un caso por nivel ESI ---------------------------------------------


@pytest.mark.parametrize("nivel", [1, 2, 3, 4, 5])
def test_arbol_de_reglas_un_caso_por_nivel(nivel):
    esi, justificacion = clasificar_por_reglas(CASOS[nivel])
    assert esi == nivel
    assert "respaldo" in justificacion


def test_arbol_de_reglas_gana_el_nivel_mas_urgente():
    # Signos de ESI 1 y también de ESI 3: manda el 1.
    e = _entrada(saturacion_oxigeno=85, escala_dolor=5)
    assert clasificar_por_reglas(e)[0] == 1


# --- La IA falla o tarda: reglas + fallback_aplicado ------------------------------------


def _falla(_prompt):
    raise ConnectionError("sin conexión")


def _lenta(_prompt):
    time.sleep(0.6)
    return json.dumps({"nivel_esi": 5, "justificacion": "Respuesta demasiado tardía."})


@pytest.mark.parametrize("nivel", [1, 2, 3, 4, 5])
def test_si_la_ia_falla_responde_el_arbol_de_reglas(nivel):
    r = engine.clasificar(CASOS[nivel], llm=RunnableLambda(_falla))

    assert r.fallback_aplicado is True
    assert r.modelo_usado == MODELO_RESPALDO == "fallback-rule-engine"
    assert r.nivel_esi_sugerido == nivel


def test_si_la_ia_tarda_mas_del_limite_responde_el_arbol_de_reglas():
    # Con un límite de 150 ms para no hacer lenta la prueba; el real es de 1500 ms.
    r = engine.clasificar(CASOS[2], llm=RunnableLambda(_lenta), timeout_ms=150)

    assert r.fallback_aplicado is True
    assert r.nivel_esi_sugerido == 2  # el de las reglas, no el 5 de la IA tardía
    assert r.latencia_ms >= 150


def test_el_limite_por_defecto_es_1500_ms():
    assert engine.TIMEOUT_MS == 1500


@pytest.mark.parametrize(
    "texto",
    [
        "esto no es json",
        '{"nivel_esi": 7, "justificacion": "Fuera del rango de ESI permitido."}',
        '{"nivel_esi": 2}',
        '{"nivel_esi": "alto", "justificacion": "El nivel no es un número."}',
        '{"nivel_esi": 2, "justificacion": "corta"}',
        "",
    ],
)
def test_una_respuesta_invalida_activa_el_respaldo(texto):
    r = engine.clasificar(CASOS[3], llm=RunnableLambda(lambda _p: texto))

    assert r.fallback_aplicado is True
    assert r.nivel_esi_sugerido == 3


def test_sin_clave_de_api_usa_el_respaldo_sin_llamar_a_internet():
    # El fixture ya quitó ANTHROPIC_API_KEY y prohíbe crear el cliente real.
    r = engine.clasificar(CASOS[4])

    assert r.fallback_aplicado is True
    assert r.nivel_esi_sugerido == 4


def test_el_respaldo_deja_aviso_en_el_log_sin_datos_del_paciente(caplog):
    caplog.set_level("WARNING", logger="meditriage.ai")
    engine.clasificar(
        _entrada(motivo="mi correo es juan@correo.cl"), llm=RunnableLambda(_falla)
    )

    registro = next(r for r in caplog.records if r.getMessage() == "ia_respaldo_aplicado")
    assert registro.motivo == "ConnectionError"
    assert "juan@correo.cl" not in caplog.text


# --- Aislamiento de memoria (Factor 06) -------------------------------------------------


def test_dos_llamadas_seguidas_no_comparten_datos():
    prompts = []

    def captura(prompt_value):
        prompts.append(prompt_value.to_string())
        return json.dumps({"nivel_esi": 3, "justificacion": "Respuesta de prueba válida."})

    llm = RunnableLambda(captura)
    a = _entrada(edad=71, sexo="masculino", sintomas=[("sintoma_unico_a", "leve")],
                 motivo="paciente A con vértigo")
    b = _entrada(edad=23, sexo="femenino", sintomas=[("sintoma_unico_b", "leve")],
                 motivo="paciente B con cefalea")

    engine.clasificar(a, llm=llm)
    engine.clasificar(b, llm=llm)

    assert len(prompts) == 2
    assert "sintoma_unico_a" in prompts[0] and "vértigo" in prompts[0]
    # La segunda llamada solo conoce al paciente B.
    assert "sintoma_unico_b" in prompts[1] and "cefalea" in prompts[1]
    for rastro in ("sintoma_unico_a", "vértigo", "71 años", "masculino"):
        assert rastro not in prompts[1]


def test_el_motor_no_guarda_estado_entre_llamadas():
    # Ningún atributo del módulo debe acumular fichas de pacientes.
    antes = {k for k, v in vars(engine).items() if isinstance(v, (list, dict, set))}
    engine.clasificar(CASOS[3], llm=_ia_responde(3))
    engine.clasificar(CASOS[2], llm=_ia_responde(2))
    despues = {k for k, v in vars(engine).items() if isinstance(v, (list, dict, set))}
    assert antes == despues


# --- Contrato: lo que NO puede llegar a la IA -------------------------------------------


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("rut", "12.345.678-5"),
        ("nombre_completo", "Juan Pérez"),
        ("email", "juan@correo.cl"),
        ("telefono", "+56912345678"),
        ("fecha_nacimiento", "1980-05-01"),
        ("prevision", "FONASA"),
        ("patient_id", "550e8400-e29b-41d4-a716-446655440000"),
    ],
)
def test_un_campo_prohibido_se_rechaza(campo, valor):
    datos = dict(
        edad_anios=40,
        signos_vitales=NORMALES,
        sintomas=[],
        **{campo: valor},
    )
    with pytest.raises(ValidationError):
        EntradaIA(**datos)


def test_el_motivo_de_consulta_sale_sanitizado():
    e = _entrada(motivo="Mi RUT es 19.876.543-2, escríbame a juan.perez@email.com o al +56912345678")
    assert "19.876.543-2" not in e.motivo_consulta
    assert "juan.perez@email.com" not in e.motivo_consulta
    assert "+56912345678" not in e.motivo_consulta


def test_la_ficha_enviada_a_la_ia_no_lleva_datos_personales():
    ficha = engine._ficha(_entrada(motivo="soy 19.876.543-2 y mi correo es a@b.cl"))
    assert "19.876.543-2" not in ficha
    assert "a@b.cl" not in ficha
    assert "Edad: 40 años" in ficha
