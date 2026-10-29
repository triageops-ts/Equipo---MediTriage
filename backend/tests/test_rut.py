import pytest

from app.core.rut import RutInvalido, calcular_dv, formatear_rut, normalizar_rut


@pytest.mark.parametrize("cuerpo,dv", [
    ("11111111", "1"),
    ("12345678", "5"),
    ("76086428", "5"),
    ("1000013", "0"),   # 11 - (suma % 11) = 11 -> "0"
    ("1000005", "K"),   # 11 - (suma % 11) = 10 -> "K"
])
def test_calcular_dv(cuerpo, dv):
    assert calcular_dv(cuerpo) == dv


def _dv_alternativo(cuerpo: str) -> str:
    """Implementación independiente: pesos 2..7 aplicados con aritmética de enteros."""
    n, suma, peso = int(cuerpo), 0, 2
    while n:
        suma += (n % 10) * peso
        n //= 10
        peso = peso + 1 if peso < 7 else 2
    r = (11 - suma % 11) % 11
    return "K" if r == 10 else str(r)


def test_calcular_dv_coincide_con_implementacion_independiente():
    for n in range(1, 30000):
        assert calcular_dv(str(n)) == _dv_alternativo(str(n))
    for n in (12345678, 99999999, 20000000, 76543210):
        assert calcular_dv(str(n)) == _dv_alternativo(str(n))


@pytest.mark.parametrize("entrada", [
    "11.111.111-1", "11111111-1", "111111111", " 11.111.111-1 ",
])
def test_formatos_validos(entrada):
    assert normalizar_rut(entrada) == "11111111-1"


def test_k_minuscula():
    assert normalizar_rut("1.000.005-k") == "1000005-K"


def test_formatear():
    assert formatear_rut("11111111-1") == "11.111.111-1"
    assert formatear_rut("1000005-K") == "1.000.005-K"


@pytest.mark.parametrize("entrada", [
    "11.111.111-2",   # DV incorrecto
    "12.345.678-9",
    "1.000.005-0",
    "", "   ", "abc", "12.345.678", "123456789012-3", "1-", "-1",
    "0-0", "00000000-0",
    "11.111.111-KK",
])
def test_invalidos(entrada):
    with pytest.raises(RutInvalido):
        normalizar_rut(entrada)


def test_mensaje_indica_dv_esperado():
    with pytest.raises(RutInvalido, match="se esperaba 1"):
        normalizar_rut("11.111.111-2")
