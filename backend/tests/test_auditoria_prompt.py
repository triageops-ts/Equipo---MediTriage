"""Contenido del registro de auditoría de la inferencia (S10-5), sin base de datos ni internet."""

from app import audit
from app.ai import engine
from app.ai.contrato import ClasificacionIA, EntradaIA

# Importados para reutilizar la base falsa y el motor falso de test_evaluate.py.
from test_evaluate import PACIENTE, _evaluar, bd, motor  # noqa: F401

# Huella de `_SISTEMA` al subir a esi-v2. Si este test falla, cambiaste el prompt:
# sube VERSION_PROMPT en engine.py y actualiza esta huella.
HUELLA_ESPERADA = "aeffcf7aac1e"


def _entrada(motivo=None) -> EntradaIA:
    return EntradaIA(
        edad_anios=45,
        sexo_biologico="femenino",
        signos_vitales={
            "presion_sistolica": 120, "presion_diastolica": 80, "frecuencia_cardiaca": 90,
            "frecuencia_respiratoria": 18, "temperatura": 37.0, "saturacion_oxigeno": 97,
            "escala_dolor": 3, "nivel_conciencia": "alerta",
        },
        sintomas=[{"codigo_sintoma": "dolor_toracico", "severidad": "moderada"}],
        motivo_consulta=motivo,
    )


def _resultado(**kw) -> ClasificacionIA:
    base = dict(
        nivel_esi_sugerido=2,
        justificacion="Dolor torácico moderado: no debe esperar.",
        modelo_usado="claude-haiku-5-5",
        latencia_ms=800,
        fallback_aplicado=False,
    )
    return ClasificacionIA(**{**base, **kw})


def test_la_huella_del_prompt_obliga_a_subir_la_version():
    assert engine.HUELLA_PROMPT == HUELLA_ESPERADA


def test_el_registro_lleva_version_modelo_ficha_y_respuesta():
    texto = engine.registro_inferencia(_entrada(), _resultado())
    assert f"version_prompt: {engine.VERSION_PROMPT} ({engine.HUELLA_PROMPT})" in texto
    assert "modelo: claude-haiku-5-5" in texto and "fallback_aplicado: no" in texto
    assert engine.ficha_enviada(_entrada()) in texto
    assert "nivel_esi: 2" in texto and "justificacion: Dolor torácico moderado" in texto


def test_el_registro_marca_el_respaldo():
    texto = engine.registro_inferencia(
        _entrada(), _resultado(modelo_usado="fallback-rule-engine", fallback_aplicado=True)
    )
    assert "modelo: fallback-rule-engine" in texto and "fallback_aplicado: si" in texto


def test_el_registro_no_lleva_rut_correo_telefono_ni_prevision():
    motivo = (
        "Paciente 12.345.678-5, correo juan@correo.cl, cel +56 9 1234 5678, "
        "beneficiario Fonasa tramo A, vive en Puente Alto. Dolor de pecho."
    )
    texto = engine.registro_inferencia(_entrada(motivo), _resultado())
    for prohibido in ("12.345.678-5", "juan@correo.cl", "1234 5678", "Fonasa", "Puente Alto"):
        assert prohibido not in texto
    assert "[RUT OCULTO]" in texto and "Dolor de pecho" in texto


def test_el_log_tecnico_de_auditoria_no_lleva_el_prompt():
    # registrar_evento solo escribe el tipo de error en el log, no el prompt.
    import inspect

    fuente = inspect.getsource(audit.registrar_evento)
    assert "prompt_enviado" not in fuente.split("except psycopg.Error")[1]


def test_evaluate_guarda_en_la_auditoria_el_registro_completo_y_sanitizado(bd, motor, monkeypatch):  # noqa: F811
    bd.episodio = (PACIENTE, "RUT 12.345.678-5 dolor de pecho desde ayer")
    llamadas = []
    original = audit.registrar_evento
    monkeypatch.setattr(
        audit, "registrar_evento", lambda cur, **kw: (llamadas.append(kw), original(cur, **kw))[1]
    )
    assert _evaluar().status_code == 201
    (kw,) = llamadas
    assert kw["evento_tipo"] == audit.EVENTO_IA_SUGERIDA and kw["sugerencia_ia"] == 2
    assert f"version_prompt: {engine.VERSION_PROMPT}" in kw["prompt_enviado"]
    assert "modelo: claude-haiku-5-5" in kw["prompt_enviado"]
    assert "12.345.678-5" not in kw["prompt_enviado"]
    assert str(PACIENTE) not in kw["prompt_enviado"]


def test_si_hubo_respaldo_el_evento_es_de_respaldo(bd, motor, monkeypatch):  # noqa: F811
    motor.resultado = _resultado(modelo_usado="fallback-rule-engine", fallback_aplicado=True)
    llamadas = []
    original = audit.registrar_evento
    monkeypatch.setattr(
        audit, "registrar_evento", lambda cur, **kw: (llamadas.append(kw), original(cur, **kw))[1]
    )
    assert _evaluar().status_code == 201
    assert llamadas[0]["evento_tipo"] == audit.EVENTO_RESPALDO_APLICADO
    assert "fallback_aplicado: si" in llamadas[0]["prompt_enviado"]
