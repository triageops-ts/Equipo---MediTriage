"""Archivo de prueba de .semgrep/meditriage-rules.yml (se ejecuta con semgrep --test).

Cada comentario "ruleid" marca una línea que la regla DEBE detectar, y cada comentario
"ok" marca una línea que NO debe detectar. Van justo antes de la línea que prueban.
"""
import logging
import os

logger = logging.getLogger("meditriage.test")


# ============================ meditriage-pii-en-logs ============================

def casos_pii_en_logs(data, rut_formateado, paciente_id, telefono):
    # --- Lo que la regla detecta ---
    # ruleid: meditriage-pii-en-logs
    logger.info(f"Paciente creado con RUT {rut_formateado}")
    # ruleid: meditriage-pii-en-logs
    logger.warning("RUT duplicado: %s", data.rut)
    # ruleid: meditriage-pii-en-logs
    logger.error("Fallo al guardar el contacto", extra={"telefono": telefono})
    # ruleid: meditriage-pii-en-logs
    logging.info("Alta de %s", data.name)
    # ruleid: meditriage-pii-en-logs
    logger.debug("Datos recibidos: %s", data.email)
    # ruleid: meditriage-pii-en-logs
    logger.info("nacimiento %s", data.birth_date)

    # --- Lo que la regla NO debe marcar ---
    # ok: meditriage-pii-en-logs
    logger.warning("patient_create_conflict")
    # ok: meditriage-pii-en-logs
    logger.info("patient_created", extra={"patient_id": str(paciente_id)})
    # ok: meditriage-pii-en-logs
    logger.info("contacto", extra={"has_contact_data": bool(data.address or data.phone or data.email)})
    # ok: meditriage-pii-en-logs
    logger.info("largo del telefono: %s", len(data.phone))
    # ok: meditriage-pii-en-logs
    logger.info("rut %s", enmascarar_rut(data.rut))
    # ok: meditriage-pii-en-logs
    logger.info("modelo cargado: %s", modelo.name)
    # ok: meditriage-pii-en-logs
    resultado = guardar(data.rut)


# ============================ meditriage-secreto-en-codigo ======================

# --- Lo que la regla detecta ---
# ruleid: meditriage-secreto-en-codigo
CLAVE = os.environ.get("APP_ENCRYPTION_KEY", "clave-de-desarrollo")
# ruleid: meditriage-secreto-en-codigo
DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/meditriage")
# ruleid: meditriage-secreto-en-codigo
APP_ENCRYPTION_KEY = "una-clave-escrita-en-el-codigo"
# ruleid: meditriage-secreto-en-codigo
cliente = anthropic.Anthropic(api_key="una-clave-cualquiera")
# ruleid: meditriage-secreto-en-codigo
RESPALDO = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"

# --- Lo que la regla NO debe marcar ---
# ok: meditriage-secreto-en-codigo
CLAVE_OK = os.environ.get("APP_ENCRYPTION_KEY")
# ok: meditriage-secreto-en-codigo
DB_OK = os.environ["DATABASE_URL"]
# ok: meditriage-secreto-en-codigo
PUERTO = os.environ.get("PORT", "8000")
# ok: meditriage-secreto-en-codigo
NIVEL = os.getenv("LOG_LEVEL", "info")
# ok: meditriage-secreto-en-codigo
cliente_ok = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def encryption_key() -> str:
    key = os.environ.get("APP_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("Falta la variable de entorno APP_ENCRYPTION_KEY.")
    return key
