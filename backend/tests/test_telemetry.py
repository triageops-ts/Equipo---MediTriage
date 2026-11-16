"""Pruebas de la instrumentación OpenTelemetry (tarjeta 13): trace_id en los logs y
atributos sin datos personales. No necesitan base de datos ni colector."""
import json
import logging
import re
from types import SimpleNamespace

from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from app.core.logging_config import JsonFormatter

HEX32 = re.compile(r"^[0-9a-f]{32}$")


def _linea() -> dict:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "evento", (), None)
    return json.loads(JsonFormatter().format(record))


def test_log_incluye_trace_id_de_32_hex_dentro_de_un_span():
    contexto = SpanContext(
        trace_id=0x0AF7651916CD43DD8448EB211C80319C,
        span_id=0xB7AD6B7169203331,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    with trace.use_span(NonRecordingSpan(contexto)):
        d = _linea()
    assert HEX32.match(d["trace_id"])
    assert d["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert d["span_id"] == "b7ad6b7169203331"


def test_log_sin_span_no_inventa_trace_id():
    assert "trace_id" not in _linea()


def test_ruta_plantilla_usa_la_plantilla_y_no_el_valor():
    from app.core.telemetry import ruta_plantilla

    scope = {"route": SimpleNamespace(path="/api/v1/patients/{rut}/consents")}
    assert ruta_plantilla(scope) == "/api/v1/patients/{rut}/consents"


def test_ruta_sin_coincidencia_se_agrupa_como_unmatched():
    from app.core.telemetry import ruta_plantilla

    assert ruta_plantilla({}) == "unmatched"


def test_el_limite_de_3_segundos_es_entero_para_que_salga_le_3():
    from app.core.telemetry import BUCKETS_SEGUNDOS

    assert 3 in BUCKETS_SEGUNDOS
    assert f"{[b for b in BUCKETS_SEGUNDOS if b == 3][0]}" == "3"
