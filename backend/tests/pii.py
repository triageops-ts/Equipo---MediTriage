"""Detector de datos personales para las pruebas de la pantalla pública (S11-11, US-04).

Busca patrones de RUT, correo y teléfono en un texto (por ejemplo, todo el JSON de una
respuesta). Los patrones son un poco más amplios que los de `app/core/sanitizer.py` a propósito:
aquí lo que importa es no dejar pasar nada. `tests/test_sala_espera_pii.py` comprueba que el
detector sí encuentra cada tipo de dato, para que una búsqueda sin resultados signifique algo.
"""
import re

PATRONES_PII: dict[str, re.Pattern] = {
    # 12.345.678-5, 12345678-5, 1.234.567-K, con o sin espacios alrededor del guion.
    "RUT": re.compile(r"(?<![\w.])\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK](?![\w])"),
    "correo": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"),
    # Celular (9 ...) o fijo de Santiago (2 ...), con o sin +56, espacios o guiones.
    "telefono": re.compile(r"(?<![\w.])(?:\+?56[\s-]?)?[92][\s-]?\d{4}[\s-]?\d{4}(?!\w)"),
}


def buscar_pii(texto: str) -> list[tuple[str, str]]:
    """Devuelve [(tipo, texto encontrado), ...]; lista vacía si no hay nada."""
    return [
        (tipo, m.group(0)) for tipo, patron in PATRONES_PII.items() for m in patron.finditer(texto)
    ]
