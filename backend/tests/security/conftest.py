"""Fixture común de las pruebas de seguridad: ninguna llama a internet ni crea un cliente real."""
import pytest

from app.ai import engine


@pytest.fixture(autouse=True)
def _sin_internet(monkeypatch):
    def _prohibido(*args, **kwargs):
        raise AssertionError("la prueba intentó crear un cliente real de Anthropic")

    monkeypatch.setattr(engine, "_cliente_anthropic", _prohibido)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)