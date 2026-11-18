from contextlib import asynccontextmanager
import logging
import os
import time
import uuid

import psycopg
import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.realtime import cerrar_cliente_redis

from app.api.v1.endpoints import auth, health, patients, triage, ws
from app.core.auth import usuario_actual
from app.core.canary import verificar_clave_cifrado
from app.core.logging_config import configure_logging, request_id_var, ruta_sin_parametros
from app.core.telemetry import (
    configure_telemetry,
    iniciar_span,
    registrar_peticion,
    ruta_plantilla,
    start_metrics_server,
)

# Factor 11: logs JSON a stdout con PII enmascarada (ver app/core/logging_config.py).
configure_logging(os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("meditriage.api")

# Observabilidad (OpenTelemetry): traces, métricas Prometheus en :9464 y trace_id en los logs.
# Solo atributos sin datos personales: método, plantilla de ruta y código de estado.
configure_telemetry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # /metrics (Prometheus) en :9464, aparte del puerto de la API y sin pasar por el Ingress.
    start_metrics_server()
    # Si la clave no coincide con los datos cifrados, el backend no arranca.
    url = os.environ.get("DATABASE_URL")
    if not url:
        # Sin base configurada no hay datos cifrados que comprobar (por ejemplo, el despliegue de práctica).
        logger.warning("key_check_skipped_no_database_url")
    else:
        try:
            conn = psycopg.connect(url)
        except psycopg.OperationalError:
            # Base no disponible (por ejemplo, en el DAST).
            logger.warning("key_check_skipped_db_unreachable")
        else:
            with conn:
                verificar_clave_cifrado(conn)
    yield
    logger.info("shutdown_iniciado")
    cerrar_cliente_redis()
    logger.info("shutdown_completo")

app = FastAPI(
    title="MediTriage API",
    version="0.1.0",
    description="Backend base para MediTriage",
    lifespan=lifespan,
)

# Públicos: /health y el login. Todo lo demás exige sesión válida (token en cookie o Bearer);
# además cada endpoint indica qué roles puede usarlo (app/core/auth.py: requiere_rol).
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1", dependencies=[Depends(usuario_actual)])
app.include_router(triage.router, prefix="/api/v1", dependencies=[Depends(usuario_actual)])
# El WebSocket valida el token él mismo (un 401 HTTP no aplica a un canal ya abierto).
app.include_router(ws.router, prefix="/api/v1")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # El id lo genera el servidor (no se confía en un header del cliente). Por la misma razón
    # no se lee `traceparent`: cada petición abre su propio trace.
    token = request_id_var.set(uuid.uuid4().hex)
    inicio = time.perf_counter()
    # El span queda activo mientras dura la petición: los logs de abajo y los de los
    # endpoints salen con su trace_id.
    with iniciar_span(request.method) as span:
        try:
            response = await call_next(request)
        except Exception as exc:
            duracion = time.perf_counter() - inicio
            registrar_peticion(span, request.method, ruta_plantilla(request.scope), 500, duracion)
            span.record_exception(exc)
            logger.error(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                    "duration_ms": round(duracion * 1000, 1),
                },
            )
            raise
        else:
            # Los valores de parámetros de ruta (/patients/{id}) no se registran.
            ruta = ruta_sin_parametros(request.url.path, request.scope.get("path_params", {}))
            duracion = time.perf_counter() - inicio
            registrar_peticion(
                span, request.method, ruta_plantilla(request.scope), response.status_code, duracion
            )
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": ruta,
                    "status": response.status_code,
                    "duration_ms": round(duracion * 1000, 1),
                },
            )
            return response
        finally:
            request_id_var.reset(token)


_PROBLEM_BASE = "https://api.meditriage.com/problems"

# Mensajes en español para los errores de tipo más comunes de Pydantic.
_MENSAJES = {
    "missing": "Campo obligatorio.",
    "extra_forbidden": "Campo no permitido.",
    "int_type": "Debe ser un número entero.",
    "int_parsing": "Debe ser un número entero.",
    "int_from_float": "Debe ser un número entero.",
    "float_type": "Debe ser un número válido.",
    "float_parsing": "Debe ser un número válido.",
    "finite_number": "Debe ser un número válido.",
    "uuid_parsing": "Debe ser un identificador UUID válido.",
    "uuid_type": "Debe ser un identificador UUID válido.",
    "string_type": "Debe ser texto.",
    "bool_type": "Debe ser verdadero o falso.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "json_invalid": "El cuerpo de la petición no es un JSON válido.",
}

def _campo(loc) -> str:
    # loc = ("body", "rut") -> "rut"
    return ".".join(str(x) for x in loc if x not in ("body", "query", "path"))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """422 con el formato de api/examples/validation-error-422.json."""
    errores = [
        {
            "field": _campo(e["loc"]),
            # Pydantic antepone "Value error, " a los mensajes de nuestros validadores.
            "message": _MENSAJES.get(e["type"], e["msg"].removeprefix("Value error, ")),
        }
        for e in exc.errors()
    ]
    logger.warning(
        "validation_failed",
        extra={
            "fields": [x["field"] for x in errores],
            "error_types": [e["type"] for e in exc.errors()],
        },
    )
    return JSONResponse(
        status_code=422,
        content={
            "type": f"{_PROBLEM_BASE}/validation-error",
            "title": "Error de validación",
            "status": 422,
            "detail": "; ".join(f"{e['field']}: {e['message']}" for e in errores),
            "instance": request.url.path,
            "errors": errores,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    titulos = {409: "Conflicto", 404: "No encontrado", 403: "Prohibido", 401: "No autorizado"}
    # No se registra exc.detail: el 409 de /patients incluye el RUT.
    if exc.status_code == 422:
        logger.warning(
            "validation_failed",
            extra={"fields": ["rut"], "error_types": ["value_error"]},
        )
    else:
        logger.warning("http_error", extra={"status": exc.status_code})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"{_PROBLEM_BASE}/{exc.status_code}",
            "title": titulos.get(exc.status_code, "Error"),
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": request.url.path,
        },
        headers=exc.headers,
    )

@app.get("/")
def root():
    return {"message": "Servidor MediTriage activo", "docs": "/docs"}

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8000))
    espera = int(os.environ.get("SHUTDOWN_TIMEOUT", 20))
    uvicorn.run(
        "main:app", host="0.0.0.0", port=puerto, reload=True, log_config=None,
        timeout_graceful_shutdown=espera,
    )