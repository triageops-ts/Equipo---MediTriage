"""Dependencias de FastAPI para exigir sesión y rol."""
import jwt
from fastapi import Depends, HTTPException, status
from starlette.requests import HTTPConnection

from app.core.security import COOKIE_NOMBRE, Usuario, leer_token

_NO_AUTORIZADO = "El token de acceso falta o no es válido."


def _extraer_token(conn: HTTPConnection) -> str | None:
    """Header `Authorization: Bearer ...` o, si no hay, la cookie httpOnly."""
    cabecera = conn.headers.get("authorization", "")
    esquema, _, valor = cabecera.partition(" ")
    if esquema.lower() == "bearer" and valor.strip():
        return valor.strip()
    return conn.cookies.get(COOKIE_NOMBRE)


def autenticar(conn: HTTPConnection) -> Usuario:
    """Devuelve el usuario del token o lanza 401. Sirve para HTTP y WebSocket."""
    token = _extraer_token(conn)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, _NO_AUTORIZADO, headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        return leer_token(token)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, _NO_AUTORIZADO, headers={"WWW-Authenticate": "Bearer"}
        ) from None


def usuario_actual(conn: HTTPConnection) -> Usuario:
    return autenticar(conn)


def requiere_rol(*roles: str):
    """Dependencia: 401 sin sesión válida, 403 si el rol no está permitido."""

    def _dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Su rol no tiene permiso para esta operación."
            )
        return usuario

    return _dependencia
