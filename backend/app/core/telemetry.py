"""Telemetría con OpenTelemetry: traces, métricas y trace_id para los logs.

Reglas de privacidad (mismas que logging_config.py):
- Los atributos de métricas y spans usan solo `method`, `route` (plantilla, p. ej.
  /api/v1/patients/{rut}) y `status_code`. Nunca la ruta con valores reales, ni
  cuerpos, ni headers, ni identificadores de pacientes.
- Una ruta que no coincide con ninguna plantilla (404) se agrupa como "unmatched"
  para no generar una serie nueva por cada URL que invente un cliente.

Qué se emite:
- Métricas: se exponen en formato Prometheus en el puerto METRICS_PORT (9464, 0 = apagado), aparte
  del puerto de la API. El Ingress solo enruta el puerto 80 del Service, así que
  /metrics no queda público; solo lo scrapea el ServiceMonitor dentro del clúster.
    meditriage_http_requests_total{method,route,status_code}              (contador)
    meditriage_http_request_duration_seconds_{bucket,sum,count}{...}      (histograma)
- Traces: un span por petición. Si OTEL_EXPORTER_OTLP_ENDPOINT está definido se envían
  por OTLP/HTTP (requiere el paquete opcional opentelemetry-exporter-otlp-proto-http);
  si no, solo viven en memoria para dar el trace_id a los logs.
- Logs: logging_config.JsonFormatter lee el span activo (solo necesita opentelemetry-api)
  y agrega `trace_id` (32 caracteres hexadecimales) y `span_id` a cada línea.
"""
import logging
import os
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Tracer
from prometheus_client import start_http_server

logger = logging.getLogger("meditriage.telemetry")

SERVICE_NAME = "meditriage-backend"
REQUESTS_METRIC = "meditriage.http.requests"
DURATION_METRIC = "meditriage.http.request.duration"

# Límites del histograma en segundos. El 3 va como ENTERO a propósito: el exporter de
# Prometheus escribe el límite con f"{valor}", así que 3 produce le="3" (3.0 produciría
# le="3.0"). Es el umbral del SLO de latencia (docs/slos.md).
BUCKETS_SEGUNDOS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10)

_tracer: Optional[Tracer] = None
_requests_counter = None
_duration_histogram = None
_configurado = False


def configure_telemetry() -> None:
    """Crea TracerProvider y MeterProvider (sin abrir puertos). Es idempotente."""
    global _tracer, _requests_counter, _duration_histogram, _configurado
    if _configurado:
        return

    recurso = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", SERVICE_NAME),
            "service.version": os.environ.get("SERVICE_VERSION", "0.1.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
        }
    )

    # --- Traces ---
    tracer_provider = TracerProvider(resource=recurso)
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except ImportError:
            logger.warning("otlp_exporter_not_installed")
    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer("meditriage.api")

    # --- Métricas ---
    lector = PrometheusMetricReader()
    vista_latencia = View(
        instrument_name=DURATION_METRIC,
        aggregation=ExplicitBucketHistogramAggregation(BUCKETS_SEGUNDOS),
    )
    meter_provider = MeterProvider(resource=recurso, metric_readers=[lector], views=[vista_latencia])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter("meditriage.api")

    _requests_counter = meter.create_counter(
        REQUESTS_METRIC,
        unit="{request}",
        description="Peticiones HTTP atendidas, por método, ruta (plantilla) y código de estado.",
    )
    _duration_histogram = meter.create_histogram(
        DURATION_METRIC,
        unit="s",
        description="Duración de las peticiones HTTP en segundos.",
    )

    _configurado = True


def start_metrics_server(puerto: Optional[int] = None) -> None:
    """Sirve /metrics en un hilo aparte. Se llama desde el lifespan de la app, no al importar:
    con `uvicorn --reload` el proceso padre también importa main.py y se quedaría con el
    puerto, mientras el hijo (el que atiende peticiones) serviría métricas vacías.
    METRICS_PORT=0 lo desactiva."""
    puerto = puerto if puerto is not None else int(os.environ.get("METRICS_PORT", "9464"))
    if puerto == 0:
        return
    try:
        start_http_server(puerto)
        logger.info("metrics_server_started", extra={"port": puerto})
    except OSError:
        # Puerto ocupado (otra instancia en la misma máquina).
        logger.warning("metrics_server_not_started", extra={"port": puerto})


def ruta_plantilla(scope: dict) -> str:
    """Plantilla de la ruta que atendió la petición (/api/v1/patients/{rut}), sin valores."""
    ruta = scope.get("route")
    plantilla = getattr(ruta, "path", None)
    return plantilla if plantilla else "unmatched"


def iniciar_span(metodo: str):
    """Abre el span de la petición (context manager). Sin telemetría configurada, no hace nada."""
    tracer = _tracer or trace.get_tracer("meditriage.api")
    return tracer.start_as_current_span(metodo, kind=SpanKind.SERVER)


def registrar_peticion(span: Span, metodo: str, ruta: str, estado: int, duracion_s: float) -> None:
    """Cierra los datos de la petición: atributos del span, contador e histograma."""
    atributos = {"method": metodo, "route": ruta, "status_code": estado}
    span.update_name(f"{metodo} {ruta}")
    span.set_attribute("http.request.method", metodo)
    span.set_attribute("http.route", ruta)
    span.set_attribute("http.response.status_code", estado)
    if estado >= 500:
        span.set_status(trace.Status(trace.StatusCode.ERROR))
    if _requests_counter is not None:
        _requests_counter.add(1, atributos)
    if _duration_histogram is not None:
        _duration_histogram.record(duracion_s, atributos)
