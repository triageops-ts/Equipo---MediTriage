"""Inicio y cierre de sesión. El token va en el cuerpo (contrato) y en una cookie httpOnly."""
import logging

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.auth import usuario_actual
from app.core.security import (
    COOKIE_NOMBRE,
    HASH_RELLENO,
    Usuario,
    cookie_segura,
    crear_token,
    verificar_password,
)
from app.db import encryption_key, get_conn_login
from app.schemas.auth import LoginInput, LoginResponse, SesionResponse

router = APIRouter(prefix="/auth", tags=["Autenticación"])
logger = logging.getLogger("meditriage.auth")

# El correo se guarda cifrado (pgcrypto): se busca descifrándolo.
_BUSCAR_USUARIO = """
    SELECT usuario_id, rol, password_hash
    FROM usuario_staff
    WHERE activo
      AND email IS NOT NULL
      AND lower(pgp_sym_decrypt(email, %(key)s::text)) = %(email)s
    LIMIT 1
"""

_CREDENCIALES_INVALIDAS = "Correo o contraseña incorrectos."


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Inicia sesión",
)
def login(data: LoginInput, response: Response, conn: psycopg.Connection = Depends(get_conn_login)):
    with conn.cursor() as cur:
        cur.execute(_BUSCAR_USUARIO, {"key": encryption_key(), "email": data.email})
        fila = cur.fetchone()

    # Se verifica siempre un hash (el de relleno si no hay usuario): mismo costo en ambos casos.
    usuario_id, rol, password_hash = fila if fila else (None, None, HASH_RELLENO)
    correcta = verificar_password(data.password, password_hash)
    if not fila or not correcta:
        logger.warning("login_fallido")  # sin correo ni contraseña en el log
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            _CREDENCIALES_INVALIDAS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, segundos = crear_token(usuario_id, rol)
    response.set_cookie(
        COOKIE_NOMBRE,
        token,
        max_age=segundos,
        httponly=True,
        samesite="strict",
        secure=cookie_segura(),
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    logger.info("login_ok", extra={"rol": rol})
    return LoginResponse(
        access_token=token, expires_in=segundos, usuario_id=usuario_id, rol=rol
    )


@router.get("/me", response_model=SesionResponse, summary="Usuario de la sesión actual")
def me(usuario: Usuario = Depends(usuario_actual)):
    """Lo usa el frontend (que no puede leer la cookie httpOnly) para saber el rol."""
    return SesionResponse(usuario_id=usuario.usuario_id, rol=usuario.rol)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cierra la sesión")
def logout(response: Response):
    response.delete_cookie(
        COOKIE_NOMBRE, path="/", httponly=True, samesite="strict", secure=cookie_segura()
    )
