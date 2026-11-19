"""Corre los 10 casos límite (S09-10) contra Claude de verdad, 3 veces cada uno.

Uso, desde la carpeta backend (la clave va en la variable de entorno, nunca en el repo):

    PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
                 python scripts/verificar_casos_limite.py
                 python scripts/verificar_casos_limite.py 6000    (opcional: límite en ms)

Para cada caso muestra los 3 niveles ESI, cuántas respuestas vinieron del RESPALDO de reglas
(no de Claude) y si cumple:
  - cada respuesta es ESI 1-5 y no menos urgente que `esi_minimo_aceptable`;
  - las 3 corridas dan el mismo nivel (consistencia).
IMPORTANTE: una respuesta del respaldo NO prueba nada sobre Claude. Si alguna viene del
respaldo, el caso queda como "SIN IA" y el script termina con código 3, aunque el nivel sea
correcto. El motivo (clave faltante, tiempo agotado, guardrail...) se muestra en la tabla.
Termina con código 1 si algún caso falla, 2 si falta la clave. Hace 30 llamadas reales.
Guarda el resultado en casos_limite_resultado.json para adjuntarlo como evidencia.
"""
import json
import logging
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.ai import engine  # noqa: E402
from app.ai.contrato import EntradaIA  # noqa: E402

CORRIDAS = 3


class _Motivos(logging.Handler):
    """Recoge el motivo de cada respaldo (tipo de error o regla), sin escribir nada en pantalla."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.motivos: list[str] = []

    def emit(self, record):
        if record.getMessage() == "ia_respaldo_aplicado":
            self.motivos.append(str(getattr(record, "motivo", "?")))


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Falta la variable de entorno ANTHROPIC_API_KEY.")
        return 2
    timeout_ms = int(sys.argv[1]) if len(sys.argv) > 1 else engine.TIMEOUT_MS
    motivos = _Motivos()
    log = logging.getLogger("meditriage.ai")
    log.addHandler(motivos)
    log.propagate = False  # sin esto Python imprime cada aviso en la consola

    casos = json.loads((RAIZ / "tests/ai/casos_limite.json").read_text(encoding="utf-8"))["casos"]
    salida, fallos, sin_ia = [], 0, 0
    print(f"Modelo: {engine._modelo()} | límite: {timeout_ms} ms | {len(casos)} casos x {CORRIDAS}\n")
    print(f"{'caso':<50}{'niveles':<12}{'min':<5}{'respaldo':<10}resultado")
    for caso in casos:
        entrada = EntradaIA(**caso["entrada"])
        motivos.motivos.clear()
        corridas = [engine.clasificar(entrada, timeout_ms=timeout_ms) for _ in range(CORRIDAS)]
        niveles = [c.nivel_esi_sugerido for c in corridas]
        respaldos = sum(c.fallback_aplicado for c in corridas)
        minimo = caso["esi_minimo_aceptable"]
        problemas = []
        if any(n > minimo for n in niveles):
            problemas.append("subclasifica")
        if len(set(niveles)) > 1:
            problemas.append("inconsistente")
        if problemas:
            fallos += 1
            veredicto = "FALLA: " + ", ".join(problemas)
        elif respaldos:
            sin_ia += 1
            veredicto = "SIN IA (respondió el respaldo)"
        else:
            veredicto = "OK"
        print(f"{caso['id']:<50}{str(niveles):<12}{minimo:<5}{respaldos:<10}{veredicto}")
        if respaldos:
            print(f"{'':<50}motivos: {', '.join(sorted(set(motivos.motivos)))}")
        salida.append({
            "id": caso["id"], "niveles": niveles, "esi_minimo_aceptable": minimo,
            "respaldos": respaldos, "motivos_respaldo": sorted(set(motivos.motivos)),
            "veredicto": veredicto,
            "justificaciones": [c.justificacion for c in corridas],
        })
    (RAIZ / "casos_limite_resultado.json").write_text(
        json.dumps(
            {"modelo": engine._modelo(), "limite_ms": timeout_ms, "resultados": salida},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    ok = len(casos) - fallos - sin_ia
    print(f"\n{ok} OK | {fallos} FALLA | {sin_ia} SIN IA (de {len(casos)} casos)")
    if sin_ia:
        print("Hay respuestas del respaldo: esos casos NO prueban cómo responde Claude.")
        return 3
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
