"""Golden set del motor de IA y su evaluación (S12-15). Sin internet."""
import json

import pytest

from app.ai.contrato import ClasificacionIA, EntradaIA
from app.ai.evaluacion import RUTA_GOLDEN, cargar_golden, evaluar, metricas
from app.ai.reglas import MODELO_RESPALDO, clasificar_por_reglas

CASOS = cargar_golden()
RUTA_LIMITE = RUTA_GOLDEN.parents[2] / "backend" / "tests" / "ai" / "casos_limite.json"


def _con_reglas(entrada: EntradaIA) -> ClasificacionIA:
    nivel, justificacion = clasificar_por_reglas(entrada)
    return ClasificacionIA(
        nivel_esi_sugerido=nivel,
        justificacion=justificacion,
        modelo_usado=MODELO_RESPALDO,
        latencia_ms=0,
        fallback_aplicado=True,
    )


def _fijo(nivel: int, respaldo: bool = False):
    def clasificar(_entrada: EntradaIA) -> ClasificacionIA:
        return ClasificacionIA(
            nivel_esi_sugerido=nivel,
            justificacion="Justificación de prueba para el nivel indicado.",
            modelo_usado=MODELO_RESPALDO if respaldo else "modelo-falso",
            latencia_ms=1,
            fallback_aplicado=respaldo,
        )

    return clasificar


# --- El archivo del golden set ---------------------------------------------------------


def test_los_ids_son_unicos_y_hay_15_casos():
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids)) == 15


def test_cada_caso_tiene_nivel_esperado_criterio_y_minimo_coherente():
    for c in CASOS:
        assert c["esi_esperado"] in (1, 2, 3, 4, 5), c["id"]
        assert c["esi_minimo_aceptable"] >= c["esi_esperado"], c["id"]
        assert len(c["criterio"].strip()) >= 20, c["id"]
        assert c["origen"] in ("bateria_guardrails_s09_10", "demo_s12_8")


def test_cubre_los_cinco_niveles_esi():
    assert {c["esi_esperado"] for c in CASOS} == {1, 2, 3, 4, 5}


def test_incluye_los_10_casos_de_la_bateria_de_guardrails_con_sus_mismos_datos():
    base = json.loads(RUTA_LIMITE.read_text(encoding="utf-8"))["casos"]
    golden = {c["id"]: c for c in CASOS}
    for b in base:
        assert b["id"] in golden
        assert golden[b["id"]]["entrada"] == b["entrada"]
        assert golden[b["id"]]["esi_minimo_aceptable"] == b["esi_minimo_aceptable"]


def test_incluye_los_5_pacientes_de_demo_uno_por_nivel():
    demo = sorted(c["esi_esperado"] for c in CASOS if c["origen"] == "demo_s12_8")
    assert demo == [1, 2, 3, 4, 5]


def test_ningun_caso_trae_datos_personales():
    texto = RUTA_GOLDEN.read_text(encoding="utf-8")
    # Los nombres de los casos demo solo viven en la descripción, nunca en la entrada a la IA.
    for c in CASOS:
        assert set(c["entrada"]) <= {
            "edad_anios", "sexo_biologico", "signos_vitales", "sintomas", "motivo_consulta",
        }
    assert "9.000.00" not in texto and "90.000.00" not in texto  # sin RUT


# --- El motor de respaldo frente al golden set -----------------------------------------


def test_el_respaldo_nunca_subclasifica_ningun_caso_del_golden_set():
    filas = evaluar(CASOS, _con_reglas)
    for f in filas:
        assert f["obtenido"] <= f["minimo_aceptable"], f["id"]
    assert metricas(filas)["global"]["subclasificados"] == 0


def test_el_respaldo_acierta_a_mas_menos_un_nivel_en_todo_el_golden_set():
    g = metricas(evaluar(CASOS, _con_reglas))["global"]
    assert g["a_mas_menos_1"] == g["n"] == 15
    assert g["respaldo"] == 15


# --- Las métricas ----------------------------------------------------------------------


def test_metricas_con_un_motor_que_siempre_responde_esi_3():
    casos = [c for c in CASOS if c["id"] in ("paro_inminente", "demo_3_camila_vergara", "demo_5_isabel_montero")]
    filas = evaluar(casos, _fijo(3))
    m = metricas(filas)
    # paro (esperado 1): sub=no, sobre=no -> obtenido 3 es MENOS urgente => subclasifica
    assert m["por_esi"][1]["subclasificados"] == 1 and m["por_esi"][1]["a_mas_menos_1"] == 0
    assert m["por_esi"][3]["exacto"] == 1
    # ESI 5 esperado y 3 obtenido: más urgente => sobreclasifica, y está a 2 niveles
    assert m["por_esi"][5]["sobreclasificados"] == 1 and m["por_esi"][5]["a_mas_menos_1"] == 0
    assert m["global"]["n"] == 3 and m["global"]["exacto"] == 1
    assert m["global"]["pct_exacto"] == 33.3


def test_metricas_cuentan_las_respuestas_del_respaldo_y_las_corridas():
    filas = evaluar(CASOS[:2], _fijo(1, respaldo=True), corridas=3)
    assert len(filas) == 6
    assert {f["corrida"] for f in filas} == {1, 2, 3}
    assert metricas(filas)["global"]["respaldo"] == 6


def test_metricas_sin_filas_no_dividen_por_cero():
    assert metricas([]) == {"global": {
        "n": 0, "exacto": 0, "a_mas_menos_1": 0, "subclasificados": 0, "sobreclasificados": 0,
        "respaldo": 0, "pct_exacto": 0.0, "pct_a_mas_menos_1": 0.0,
    }, "por_esi": {}}


def test_un_caso_con_campos_de_mas_se_rechaza_al_cargar(tmp_path):
    ruta = tmp_path / "g.json"
    ruta.write_text(json.dumps({"casos": [{"id": "x", "entrada": {"edad_anios": 30, "rut": "1-9",
        "signos_vitales": {}}}]}), encoding="utf-8")
    with pytest.raises(Exception):
        cargar_golden(ruta)
