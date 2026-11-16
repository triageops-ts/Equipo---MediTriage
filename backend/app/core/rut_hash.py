import hashlib
import hmac
import os


def calcular_rut_hash(rut_formateado: str) -> str:
    """HMAC-SHA256 del RUT ya normalizado (formatear_rut), con clave aparte."""
    key = os.environ.get("APP_RUT_HASH_KEY")
    if not key:
        raise RuntimeError("Falta la variable de entorno APP_RUT_HASH_KEY.")
    return hmac.new(key.encode(), rut_formateado.encode(), hashlib.sha256).hexdigest()