import os

import pytest

# Clave de firma solo para las pruebas.
os.environ.setdefault("JWT_SECRET", "clave-de-pruebas-0123456789-0123456789-abcdef")
os.environ.setdefault("APP_RUT_HASH_KEY", "clave-hash-rut-de-pruebas-0123456789")


@pytest.fixture(autouse=True)
def _reiniciar_rate_limit():
    """Cada prueba parte con los contadores del límite de peticiones en cero (S11-1)."""
    from app.core.rate_limit import limitador

    limitador.reiniciar()
    yield
    limitador.reiniciar()