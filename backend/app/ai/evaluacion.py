"""Evaluación del motor de IA contra el golden set (S12-15).

Corre cada caso del golden set por `engine.clasificar` y calcula:
  - acierto exacto: el nivel sugerido es igual al esperado;
  - acierto a ±1 nivel: el nivel sugerido difiere como máximo en 1;
  - subclasificación: el nivel sugerido es MENOS urgente que el esperado (error grave);
  - sobreclasificación: es MÁS urgente que el esperado (se tolera, pero se mide);
  - respuestas del respaldo de reglas (no de Claude), para no confundir lo que se midió.

La lógica vive aquí para poder probarla sin internet; `scripts/evaluar_golden_set.py` es solo
la línea de comandos.
"""
import json
from collections import defaultdict
from pathlib import Path
from typing import Callable

from app.ai.contrato import ClasificacionIA, EntradaIA

RUTA_GOLDEN = Path(__file__).resolve().parents[3] / "docs" / "ia" / "golden-set.json"


def cargar_golden(ruta: Path = RUTA_GOLDEN) -> list[dict]:
    """Lee los casos del golden set y valida que cada entrada cumpla el contrato de la IA."""
    casos = json.loads(ruta.read_text(encoding="utf-8"))["casos"]
    for caso in casos:
        EntradaIA(**caso["entrada"])
    return casos


def evaluar(
    casos: list[dict],
    clasificar: Callable[[EntradaIA], ClasificacionIA],
    corridas: int = 1,
) -> list[dict]:
    """Una fila por caso y por corrida, con el nivel sugerido y quién respondió."""
    filas = []
    for caso in casos:
        entrada = EntradaIA(**caso["entrada"])
        for corrida in range(1, corridas + 1):
            r = clasificar(entrada)
            filas.append({
                "id": caso["id"],
                "corrida": corrida,
                "esperado": caso["esi_esperado"],
                "minimo_aceptable": caso["esi_minimo_aceptable"],
                "obtenido": r.nivel_esi_sugerido,
                "modelo": r.modelo_usado,
                "respaldo": r.fallback_aplicado,
                "latencia_ms": r.latencia_ms,
            })
    return filas


def _resumir(filas: list[dict]) -> dict:
    n = len(filas)
    exacto = sum(f["obtenido"] == f["esperado"] for f in filas)
    cerca = sum(abs(f["obtenido"] - f["esperado"]) <= 1 for f in filas)
    sub = sum(f["obtenido"] > f["esperado"] for f in filas)
    sobre = sum(f["obtenido"] < f["esperado"] for f in filas)
    respaldo = sum(f["respaldo"] for f in filas)
    return {
        "n": n,
        "exacto": exacto,
        "a_mas_menos_1": cerca,
        "subclasificados": sub,
        "sobreclasificados": sobre,
        "respaldo": respaldo,
        "pct_exacto": round(100 * exacto / n, 1) if n else 0.0,
        "pct_a_mas_menos_1": round(100 * cerca / n, 1) if n else 0.0,
    }


def metricas(filas: list[dict]) -> dict:
    """Métricas globales y por nivel ESI esperado (claves 1 a 5)."""
    por_nivel = defaultdict(list)
    for f in filas:
        por_nivel[f["esperado"]].append(f)
    return {
        "global": _resumir(filas),
        "por_esi": {nivel: _resumir(por_nivel[nivel]) for nivel in sorted(por_nivel)},
    }
