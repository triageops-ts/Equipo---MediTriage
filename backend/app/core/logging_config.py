"""Logging estructurado en JSON a stdout, con PII enmascarada (Factor 11).

Solo usa la librería estándar: no agrega dependencias ni toca el Dockerfile.

Reglas:
- Una línea JSON por evento, siempre a stdout (nunca a archivos).
- Todo texto que sale pasa por `mascarar_texto`: RUT, correos y teléfonos
  se reemplazan antes de escribirse. Incluye mensajes, campos extra y tracebacks.
- Los campos extra cuyo nombre es PII (rut, nombre, email, ...) se reemplazan
  completos, sin importar su valor.
- Este log es técnico. El audit log de negocio vive aparte, en Postgres.
"""
import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

MASCARA = "[REDACTED]"

# Identifica cada petición en todos los logs que genera (lo fija el middleware).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Nombres de campo que nunca se escriben, ni en `extra` ni dentro de dicts anidados.
CAMPOS_PII = frozenset(
    {
        "rut", "run", "name", "nombre", "nombre_completo", "full_name",
        "email", "correo", "phone", "telefono", "address", "direccion",
        "birth_date", "fecha_nacimiento", "firma_digital", "password",
        "contrasena", "token", "authorization", "api_key",
        "app_encryption_key", "database_url", "key",
    }
)

# RUT con o sin puntos/guion: 12.345.678-5, 12345678-5, 123456785.
_RUT = re.compile(r"(?<![\w-])\d{1,2}(?:\.?\d{3}){2}-?[\dkK](?![\w-])")
_EMAIL = re.compile(r"[^@\s\"']+@[^@\s\"']+\.[^@\s\"']+")
# Móvil chileno: +56 9 1234 5678 / 9 1234 5678 / 912345678.
_TELEFONO = re.compile(r"(?<![\w-])(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?![\w-])")

# Atributos estándar de LogRecord: lo que no está aquí es un campo `extra`.
# `color_message` lo agrega uvicorn (el mismo texto con códigos ANSI): es ruido.
_ESTANDAR = frozenset(
    vars(logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None))
) | {"message", "asctime", "taskName", "color_message"}


def mascarar_texto(texto: str) -> str:
    texto = _EMAIL.sub(MASCARA, texto)
    texto = _RUT.sub(MASCARA, texto)
    return _TELEFONO.sub(MASCARA, texto)


def ruta_sin_parametros(path: str, params: dict) -> str:
    """/patients/abc123 -> /patients/{patient_id}: el valor real nunca llega al log."""
    nombres = {str(v): k for k, v in params.items()}
    return "/".join("{" + nombres[s] + "}" if s in nombres else s for s in path.split("/"))


def _sanear(valor: Any) -> Any:
    if isinstance(valor, str):
        return mascarar_texto(valor)
    if isinstance(valor, dict):
        return {
            str(k): MASCARA if str(k).lower() in CAMPOS_PII else _sanear(v)
            for k, v in valor.items()
        }
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [_sanear(v) for v in valor]
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor
    return mascarar_texto(str(valor))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        evento: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mascarar_texto(record.getMessage()),
            "request_id": request_id_var.get(),
        }
        for campo, valor in record.__dict__.items():
            if campo in _ESTANDAR or campo.startswith("_"):
                continue
            evento[campo] = MASCARA if campo.lower() in CAMPOS_PII else _sanear(valor)
        if record.exc_info:
            # Se registra el tipo y el traceback enmascarado: el texto de la
            # excepción puede traer datos del paciente.
            evento["exception"] = mascarar_texto(self.formatException(record.exc_info))
        return json.dumps(evento, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Deja todos los logs (app y uvicorn) como JSON en stdout. Es idempotente."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    raiz = logging.getLogger()
    raiz.handlers = [handler]
    raiz.setLevel(level)

    # Uvicorn instala sus propios handlers: se reemplazan para que también
    # salgan en JSON y enmascarados.
    for nombre in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(nombre)
        lg.handlers = [handler]
        lg.propagate = False
        lg.setLevel(level)

    # El access log de uvicorn incluye la IP del cliente y la ruta completa.
    # Se reemplaza por el log de petición del middleware (método, ruta, estado).
    acceso = logging.getLogger("uvicorn.access")
    acceso.handlers = []
    acceso.propagate = False
    acceso.disabled = True
