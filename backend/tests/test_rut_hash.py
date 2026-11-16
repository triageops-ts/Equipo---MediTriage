from app.core.rut_hash import calcular_rut_hash


def test_mismo_rut_mismo_hash(monkeypatch):
    monkeypatch.setenv("APP_RUT_HASH_KEY", "k1")
    h = calcular_rut_hash("12.345.678-5")
    assert h == calcular_rut_hash("12.345.678-5")
    assert len(h) == 64


def test_otra_clave_otro_hash(monkeypatch):
    monkeypatch.setenv("APP_RUT_HASH_KEY", "k1")
    h1 = calcular_rut_hash("12.345.678-5")
    monkeypatch.setenv("APP_RUT_HASH_KEY", "k2")
    assert calcular_rut_hash("12.345.678-5") != h1