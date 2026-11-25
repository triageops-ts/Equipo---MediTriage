"""Evalúa el motor de IA contra el golden set (S12-15) y muestra el acierto por nivel ESI.

Uso, desde la carpeta backend:

    python scripts/evaluar_golden_set.py                   (1 corrida por caso)
    python scripts/evaluar_golden_set.py --corridas 3
    python scripts/evaluar_golden_set.py --json salida.json

Usa el motor tal como está configurado: con ANTHROPIC_API_KEY responde Claude; sin ella (o si
Claude falla, tarda más de 1500 ms o rompe un guardrail) responde el respaldo de reglas. Cada fila
indica quién respondió, y el resumen cuenta las respuestas del respaldo: una evaluación hecha solo
con el respaldo describe el árbol de reglas, no a Claude.

Códigos de salida: 0 sin subclasificación; 1 si algún caso salió menos urgente que lo esperado.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.ai import engine  # noqa: E402
from app.ai.evaluacion import cargar_golden, evaluar, metricas  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa el motor de IA contra el golden set.")
    parser.add_argument("--corridas", type=int, default=1, help="veces que se corre cada caso")
    parser.add_argument("--json", help="guarda las filas y las métricas en este archivo")
    args = parser.parse_args()

    logging.disable(logging.CRITICAL)  # sin avisos del motor en pantalla

    casos = cargar_golden()
    filas = evaluar(casos, engine.clasificar, corridas=args.corridas)
    m = metricas(filas)

    print(f"Modelo configurado: {engine._modelo()} | casos: {len(casos)} | corridas: {args.corridas}\n")
    print(f"{'caso':<48}{'esp':<5}{'obt':<5}{'quién respondió'}")
    for f in filas:
        quien = "respaldo de reglas" if f["respaldo"] else f["modelo"]
        marca = ""
        if f["obtenido"] > f["esperado"]:
            marca = "  <- SUBCLASIFICA"
        elif f["obtenido"] < f["esperado"]:
            marca = "  (sobreclasifica)"
        print(f"{f['id']:<48}{f['esperado']:<5}{f['obtenido']:<5}{quien}{marca}")

    def fila(nombre, r):
        exacto = f"{r['exacto']}/{r['n']} ({r['pct_exacto']}%)"
        cerca = f"{r['a_mas_menos_1']}/{r['n']} ({r['pct_a_mas_menos_1']}%)"
        return f"{nombre:<14}{r['n']:<7}{exacto:<16}{cerca:<16}{r['subclasificados']:<5}{r['sobreclasificados']:<7}{r['respaldo']}/{r['n']}"

    print(f"\n{'ESI esperado':<14}{'casos':<7}{'exacto':<16}{'a ±1 nivel':<16}{'sub':<5}{'sobre':<7}respaldo")
    for nivel, r in m["por_esi"].items():
        print(fila(str(nivel), r))
    g = m["global"]
    print(fila("TOTAL", g))
    if g["respaldo"] == g["n"]:
        print("\nTodas las respuestas vinieron del respaldo de reglas: esta evaluación describe el árbol de reglas, no a Claude.")
    elif g["respaldo"]:
        print(f"\n{g['respaldo']} de {g['n']} respuestas vinieron del respaldo de reglas (no de Claude).")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"modelo": engine._modelo(), "filas": filas, "metricas": m}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nResultado guardado en {args.json}")
    return 1 if g["subclasificados"] else 0


if __name__ == "__main__":
    sys.exit(main())
