import re

_FORMATO = re.compile(r"^(\d{1,8})([0-9K])$")


class RutInvalido(ValueError):
    """El RUT no está bien formado. El mensaje es apto para mostrarse al usuario."""


def calcular_dv(cuerpo: str) -> str:
    suma = 0
    factor = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def normalizar_rut(rut: str) -> str:
    """Devuelve el RUT canónico `12345678-K` o lanza RutInvalido."""
    if not isinstance(rut, str) or not rut.strip():
        raise RutInvalido("El RUT es obligatorio.")

    limpio = re.sub(r"[.\-\s]", "", rut).upper()
    coincidencia = _FORMATO.match(limpio)
    if not coincidencia:
        raise RutInvalido(
            "El RUT no tiene un formato válido. Use por ejemplo 12.345.678-5 "
            "(hasta 8 dígitos más el dígito verificador, que puede ser K)."
        )

    cuerpo, dv = coincidencia.groups()
    if int(cuerpo) == 0:
        raise RutInvalido("El RUT no es válido: el número no puede ser cero.")

    esperado = calcular_dv(cuerpo)
    if dv != esperado:
        raise RutInvalido(
            f"El RUT no es válido: el dígito verificador no corresponde "
            f"(se esperaba {esperado})."
        )
    return f"{int(cuerpo)}-{dv}"


def formatear_rut(rut_normalizado: str) -> str:
    cuerpo, dv = rut_normalizado.split("-")
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"