"""Pruebas de la cadena de hashes (no necesitan base de datos)."""
import uuid
from datetime import datetime

from app.core.audit_chain import HASH_GENESIS, calcular_hash, verificar_cadena

EP = uuid.UUID("11111111-1111-1111-1111-111111111111")
FECHA = datetime(2026, 11, 14, 12, 0, 0, 123456)


def _registro(anterior: str, n: int) -> dict:
    base = dict(
        evento_tipo="decision_guardado_fallido",
        entidad_afectada="episodio_triage",
        entidad_id=EP,
        usuario_id=None,
        detalle_json={"intentos": n, "tipo_error": "red", "recuperado": False},
        fecha_hora_evento=FECHA.replace(second=n),
    )
    h = calcular_hash(
        hash_anterior=anterior,
        evento_tipo=base["evento_tipo"],
        entidad_afectada=base["entidad_afectada"],
        entidad_id=base["entidad_id"],
        usuario_id=base["usuario_id"],
        detalle=base["detalle_json"],
        fecha_hora_evento=base["fecha_hora_evento"],
    )
    return {**base, "hash_anterior": anterior, "hash_actual": h}


def _cadena(largo: int) -> list[dict]:
    regs, anterior = [], HASH_GENESIS
    for n in range(1, largo + 1):
        r = _registro(anterior, n)
        regs.append(r)
        anterior = r["hash_actual"]
    return regs


def test_hash_es_determinista_y_de_64_caracteres():
    a = _registro(HASH_GENESIS, 1)["hash_actual"]
    b = _registro(HASH_GENESIS, 1)["hash_actual"]
    assert a == b and len(a) == 64


def test_orden_de_las_claves_del_detalle_no_cambia_el_hash():
    kw = dict(
        hash_anterior=HASH_GENESIS, evento_tipo="x", entidad_afectada="y",
        entidad_id=EP, usuario_id=None, fecha_hora_evento=FECHA,
    )
    assert calcular_hash(detalle={"a": 1, "b": 2}, **kw) == calcular_hash(detalle={"b": 2, "a": 1}, **kw)


def test_cadena_integra():
    assert verificar_cadena(_cadena(4)) is None


def test_detecta_registro_alterado():
    regs = _cadena(4)
    regs[2]["detalle_json"] = {"intentos": 99, "tipo_error": "red", "recuperado": True}
    assert verificar_cadena(regs) == 2


def test_detecta_registro_borrado():
    regs = _cadena(4)
    del regs[1]
    assert verificar_cadena(regs) == 1