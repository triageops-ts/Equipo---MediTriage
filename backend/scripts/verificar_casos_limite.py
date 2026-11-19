"""Corre los 10 casos límite (S09-10) contra Claude de verdad, 3 veces cada uno.

Uso, desde la carpeta backend (la clave va en la variable de entorno, nunca en el repo):

    PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
                 python scripts/verificar_casos_limite.py

Para cada caso muestra los 3 niveles ESI que devolvió, si hubo respaldo y si cumple:
  - cada respuesta es ESI 1-5 y no menos urgente que `esi_minimo_aceptable`;
  - las 3 corridas dan el mismo nivel (consistencia).
Termina con código 1 si algún caso falla. Hace 30 llamadas reales (unos centavos).
Guarda el resultado en casos_limite_resultado.json para adjuntarlo como evidencia.
"""
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.ai import engine  # noqa: E402
from app.ai.contrato import EntradaIA  # noqa: E402

CORRIDAS = 3


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Falta la variable de entorno ANTHROPIC_API_KEY.")
        return 2
    casos = json.loads((RAIZ / "tests/ai/casos_limite.json").read_text(encoding="utf-8"))["casos"]
    salida, fallos = [], 0
    print(f"Modelo: {engine._modelo()} | {len(casos)} casos x {CORRIDAS} corridas\n")
    print(f"{'caso':<52}{'niveles':<12}{'min':<5}{'respaldo':<10}resultado")
    for caso in casos:
        entrada = EntradaIA(**caso["entrada"])
        corridas = [engine.clasificar(entrada) for _ in range(CORRIDAS)]
        niveles = [c.nivel_esi_sugerido for c in corridas]
        respaldos = sum(c.fallback_aplicado for c in corridas)
        minimo = caso["esi_minimo_aceptable"]
        motivos = []
        if any(n > minimo for n in niveles):
            motivos.append("subclasifica")
        if len(set(niveles)) > 1:
            motivos.append("inconsistente")
        if respaldos:
            motivos.append(f"respaldo x{respaldos}")
        ok = not [m for m in motivos if not m.startswith("respaldo")]
        fallos += not ok
        print(f"{caso['id']:<52}{str(niveles):<12}{minimo:<5}{respaldos:<10}"
              f"{'OK' if ok else 'FALLA: ' + ', '.join(motivos)}")
        salida.append({
            "id": caso["id"], "niveles": niveles, "esi_minimo_aceptable": minimo,
            "respaldos": respaldos, "ok": ok,
            "justificaciones": [c.justificacion for c in corridas],
        })
    (RAIZ / "casos_limite_resultado.json").write_text(
        json.dumps({"modelo": engine._modelo(), "resultados": salida}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{len(casos) - fallos}/{len(casos)} casos OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
