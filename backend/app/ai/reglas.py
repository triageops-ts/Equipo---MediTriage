"""Árbol de reglas heurísticas del ESI: respaldo determinista cuando falla la IA.

No usa red ni IA: mismo ingreso, mismo resultado. Se activa si Claude falla, tarda más
de 1500 ms o devuelve algo inválido, para que la enfermera nunca quede esperando.

Es una aproximación del ESI con umbrales fisiológicos de adulto, pensada para pecar
de prudente (ante la duda, el nivel más urgente). NO reemplaza el juicio clínico y los
umbrales deben ser revisados por el equipo clínico antes de un uso real. Para niños los
rangos normales son otros: con estos umbrales tenderá a sobreclasificar, no a subclasificar.
"""
from app.ai.contrato import EntradaIA

MODELO_RESPALDO = "fallback-rule-engine"


def _criterios(e: EntradaIA) -> dict[int, list[str]]:
    """Devuelve, por nivel ESI, los criterios que se cumplen."""
    v = e.signos_vitales
    s = e.sintomas
    c: dict[int, list[str]] = {1: [], 2: [], 3: [], 4: []}

    # ESI 1: requiere intervención inmediata para salvar la vida.
    if v.nivel_conciencia in ("inconsciente", "dolor"):
        c[1].append(f"nivel de conciencia '{v.nivel_conciencia}'")
    if v.saturacion_oxigeno < 90:
        c[1].append(f"saturación de oxígeno {v.saturacion_oxigeno}%")
    if v.presion_sistolica < 80:
        c[1].append(f"presión sistólica {v.presion_sistolica} mmHg")
    if v.frecuencia_respiratoria < 8 or v.frecuencia_respiratoria > 35:
        c[1].append(f"frecuencia respiratoria {v.frecuencia_respiratoria}/min")
    if v.frecuencia_cardiaca < 40 or v.frecuencia_cardiaca > 150:
        c[1].append(f"frecuencia cardíaca {v.frecuencia_cardiaca} lpm")

    # ESI 2: situación de alto riesgo que no debe esperar.
    if v.nivel_conciencia == "verbal":
        c[2].append("responde solo a estímulos verbales")
    if 90 <= v.saturacion_oxigeno < 94:
        c[2].append(f"saturación de oxígeno {v.saturacion_oxigeno}%")
    if 80 <= v.presion_sistolica < 90 or v.presion_sistolica > 220:
        c[2].append(f"presión sistólica {v.presion_sistolica} mmHg")
    if 40 <= v.frecuencia_cardiaca < 50 or 130 < v.frecuencia_cardiaca <= 150:
        c[2].append(f"frecuencia cardíaca {v.frecuencia_cardiaca} lpm")
    if 8 <= v.frecuencia_respiratoria < 10 or 30 < v.frecuencia_respiratoria <= 35:
        c[2].append(f"frecuencia respiratoria {v.frecuencia_respiratoria}/min")
    if v.temperatura >= 40 or v.temperatura < 35:
        c[2].append(f"temperatura {v.temperatura} °C")
    if v.escala_dolor >= 8:
        c[2].append(f"dolor {v.escala_dolor}/10")
    if any(x.severidad == "severa" for x in s):
        c[2].append("síntoma de severidad severa")

    # ESI 3: estable, pero con alteraciones o varios recursos esperables.
    if 94 <= v.saturacion_oxigeno < 96:
        c[3].append(f"saturación de oxígeno {v.saturacion_oxigeno}%")
    if 180 < v.presion_sistolica <= 220:
        c[3].append(f"presión sistólica {v.presion_sistolica} mmHg")
    if 100 < v.frecuencia_cardiaca <= 130 or 50 <= v.frecuencia_cardiaca < 60:
        c[3].append(f"frecuencia cardíaca {v.frecuencia_cardiaca} lpm")
    if 20 < v.frecuencia_respiratoria <= 30 or 10 <= v.frecuencia_respiratoria < 12:
        c[3].append(f"frecuencia respiratoria {v.frecuencia_respiratoria}/min")
    if 38 <= v.temperatura < 40 or 35 <= v.temperatura < 36:
        c[3].append(f"temperatura {v.temperatura} °C")
    if 4 <= v.escala_dolor < 8:
        c[3].append(f"dolor {v.escala_dolor}/10")
    if len(s) >= 2:
        c[3].append(f"{len(s)} síntomas simultáneos")

    # ESI 4: un solo problema, sin alteraciones relevantes.
    if len(s) == 1:
        c[4].append("un síntoma aislado")
    if 1 <= v.escala_dolor < 4:
        c[4].append(f"dolor {v.escala_dolor}/10")

    return c


def clasificar_por_reglas(entrada: EntradaIA) -> tuple[int, str]:
    """Devuelve (nivel_esi, justificación). Gana el nivel más urgente que se cumpla."""
    criterios = _criterios(entrada)
    for nivel in (1, 2, 3, 4):
        if criterios[nivel]:
            motivos = "; ".join(criterios[nivel])
            return nivel, (
                f"Clasificación por reglas de respaldo (sin IA): {motivos}."
            )
    return 5, (
        "Clasificación por reglas de respaldo (sin IA): signos vitales normales "
        "y sin síntomas registrados."
    )
