"""Guardrails del motor de IA (Tarjeta S09-10).

Son reglas deterministas que impiden que la IA entregue algo fuera de lo esperado. Se aplican
a la respuesta de Claude ANTES de usarla; si alguna se rompe, el motor descarta la respuesta,
usa el árbol de reglas de respaldo (`reglas.py`) y lo deja marcado con `fallback_aplicado=True`.

Reglas de salida (`validar_salida`):
  G1  El nivel ESI es un entero entre 1 y 5.
  G2  La justificación no está vacía (ni solo espacios).
  G3  Si hay un signo vital crítico (SpO2 muy baja, presión sistólica crítica, inconsciencia,
      etc.), el ESI nunca puede ser 4 ni 5.
  G4  Si hay un signo vital crítico, la justificación no puede decir que el paciente está
      estable, normal o sin riesgo (contradice los signos vitales).
  G5  La justificación no puede apoyarse en variables socioeconómicas, geográficas ni
      previsionales (Fonasa/Isapre, ingresos, comuna...).

Entrada (`redactar_variables_prohibidas`): el texto libre del paciente se limpia de esas
mismas variables antes de armar el prompt, para que nunca lleguen a la IA.

"Crítico" = cumple algún criterio de ESI 1 del árbol de reglas (`reglas.py`), así hay una sola
definición de crítico en todo el motor. Los umbrales deben ser revisados por el equipo clínico.
"""
import re
from dataclasses import dataclass
from typing import Optional

from app.ai.contrato import EntradaIA, SalidaIA
from app.ai.reglas import criterios_por_nivel

# Con criterios críticos el ESI debe ser 1, 2 o 3: nunca 4 ni 5.
NIVEL_MAXIMO_CON_CRITICOS = 3

MARCADOR_OMITIDO = "[OMITIDO]"

# Variables que no pueden influir en la clasificación: previsión de salud, nivel
# socioeconómico y ubicación geográfica. Las expresiones aceptan con y sin tilde.
# Se evitan palabras clínicas legítimas ("región torácica", "ingreso" hospitalario...).
_PROHIBIDAS = re.compile(
    r"\b(?:"
    r"fonasa|isapre|banm[eé]dica|colmena|consalud|cruz\s+blanca|vida\s+tres"
    r"|previsi[oó]n(?:al(?:es)?)?|tramo\s+[abcd]"
    r"|socioecon[oó]mic[oa]s?|nivel\s+de\s+ingresos?|(?:bajos|altos)\s+ingresos|ingresos\s+(?:bajos|altos|mensuales|familiares)|sueldo|pobreza|cesante|desemplead[oa]"
    r"|comuna|domicilio|barrio"
    r"|(?:vivo|vive|viven|vivimos)\s+en(?:\s+\w+){1,3}"
    r")\b",
    re.IGNORECASE,
)

# Frases que afirman estabilidad: contradicen un signo vital crítico (G4).
_ESTABILIDAD = re.compile(
    r"\b(?:estable|estables|sin\s+alteraciones|sin\s+riesgo|no\s+urgente|"
    r"signos\s+vitales\s+(?:normales|dentro\s+de\s+(?:lo\s+)?(?:normal|rangos?\s+normales?)))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violacion:
    """Regla rota. `regla` va al log; `detalle` nunca contiene datos del paciente."""

    regla: str
    detalle: str


def criterios_criticos(entrada: EntradaIA) -> list[str]:
    """Signos que ponen al paciente en ESI 1 según el árbol de reglas."""
    return criterios_por_nivel(entrada)[1]


def tiene_variables_prohibidas(texto: str) -> bool:
    return bool(_PROHIBIDAS.search(texto or ""))


def redactar_variables_prohibidas(texto: str) -> str:
    """Reemplaza por [OMITIDO] previsión, socioeconomía y ubicación del texto libre."""
    return _PROHIBIDAS.sub(MARCADOR_OMITIDO, texto)


def validar_salida(entrada: EntradaIA, salida: SalidaIA) -> Optional[Violacion]:
    """Devuelve la primera regla rota, o None si la respuesta de la IA es aceptable."""
    nivel = salida.nivel_esi
    if isinstance(nivel, bool) or not isinstance(nivel, int) or not 1 <= nivel <= 5:
        return Violacion("G1_NIVEL_FUERA_DE_RANGO", "el nivel ESI no es un entero entre 1 y 5")

    justificacion = (salida.justificacion or "").strip()
    if not justificacion:
        return Violacion("G2_JUSTIFICACION_VACIA", "la justificación está vacía")

    criticos = criterios_criticos(entrada)
    if criticos and nivel > NIVEL_MAXIMO_CON_CRITICOS:
        return Violacion(
            "G3_CRITICO_SUBCLASIFICADO",
            f"hay {len(criticos)} signo(s) crítico(s) y la IA respondió ESI {nivel}",
        )
    if criticos and _ESTABILIDAD.search(justificacion):
        return Violacion(
            "G4_JUSTIFICACION_INCOHERENTE",
            "la justificación dice que el paciente está estable con signos críticos",
        )
    if tiene_variables_prohibidas(justificacion):
        return Violacion(
            "G5_VARIABLE_PROHIBIDA",
            "la justificación menciona previsión, nivel socioeconómico o ubicación",
        )
    return None
