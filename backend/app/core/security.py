"""Autenticación: hash de contraseñas (bcrypt) y token JWT firmado (HS256).

El token lleva el id del usuario (`sub`) y su rol. La clave de firma sale de la
variable de entorno JWT_SECRET (nunca va en el repo).
"""
import os
import time
from dataclasses import dataclass
from uuid import UUID

import bcrypt
import jwt

ALGORITMO = "HS256"
ROLES = ("enfermero", "medico", "auditor")
COOKIE_NOMBRE = "access_token"
# bcrypt solo usa los primeros 72 bytes; se rechaza más largo para no truncar en silencio.
MAX_BYTES_PASSWORD = 72


@dataclass(frozen=True)
class Usuario:
    usuario_id: UUID
    rol: str


def jwt_secret() -> str:
    secreto = os.environ.get("JWT_SECRET")
    if not secreto:
        raise RuntimeError("Falta la variable de entorno JWT_SECRET.")
    return secreto


def minutos_token() -> int:
    return int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))


def cookie_segura() -> bool:
    # En producción (HTTPS) debe ser true. Por defecto false para poder usar http://localhost.
    return os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_password(password: str, password_hash: str | None) -> bool:
    """True si la contraseña coincide. Nunca lanza: un hash ausente o dañado es False."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


# Hash de relleno: si el correo no existe se verifica igual contra este hash, para que
# el tiempo de respuesta no revele si el usuario existe.
HASH_RELLENO = hash_password("relleno-sin-usuario")


def crear_token(usuario_id: UUID | str, rol: str) -> tuple[str, int]:
    """Devuelve (token, segundos de vigencia)."""
    segundos = minutos_token() * 60
    ahora = int(time.time())
    token = jwt.encode(
        {"sub": str(usuario_id), "rol": rol, "iat": ahora, "exp": ahora + segundos},
        jwt_secret(),
        algorithm=ALGORITMO,
    )
    return token, segundos


def leer_token(token: str) -> Usuario:
    """Valida firma y expiración. Lanza jwt.PyJWTError / ValueError si no es válido."""
    datos = jwt.decode(
        token,
        jwt_secret(),
        algorithms=[ALGORITMO],  # fija el algoritmo: evita "alg: none"
        options={"require": ["exp", "sub"]},
    )
    rol = datos.get("rol")
    if rol not in ROLES:
        raise ValueError("Rol desconocido en el token.")
    return Usuario(usuario_id=UUID(datos["sub"]), rol=rol)
