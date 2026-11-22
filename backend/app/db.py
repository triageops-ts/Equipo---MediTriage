import os

import psycopg
from fastapi import Depends

from app.core.auth import usuario_actual
from app.core.security import Usuario

# Contexto interno solo para el login (leer usuario_staff antes de conocer el rol).
ROL_AUTENTICACION = "autenticacion"
# Contexto interno de la pantalla pública (sin token): solo lee episodios, clasificación y
# decisión (migración 0013). No ve paciente, contactos ni usuario_staff.
ROL_SALA_ESPERA = "sala_espera"


def encryption_key() -> str:
    key = os.environ.get("APP_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("Falta la variable de entorno APP_ENCRYPTION_KEY.")
    return key


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta la variable de entorno DATABASE_URL.")
    return url


def set_rls_context(conn: psycopg.Connection, rol: str, usuario_id=None) -> None:
    """Fija app.rol y app.usuario_id solo para la transacción actual (equivale a SET LOCAL).

    set_config(..., true) permite pasar parámetros; SET LOCAL no. Al hacer commit o
    rollback las variables desaparecen, así que no se filtran a otra petición del pool.
    """
    conn.execute(
        "SELECT set_config('app.rol', %s, true), set_config('app.usuario_id', %s, true)",
        (rol, str(usuario_id) if usuario_id else ""),
    )


def get_conn(usuario: Usuario = Depends(usuario_actual)):
    """Conexión con el rol y el id del token ya aplicados (S09-2)."""
    with psycopg.connect(_database_url()) as conn:
        set_rls_context(conn, usuario.rol, usuario.usuario_id)
        yield conn


def get_conn_login():
    """Solo para /login: aún no hay token, y el rol interno solo puede leer usuario_staff."""
    with psycopg.connect(_database_url()) as conn:
        set_rls_context(conn, ROL_AUTENTICACION)
        yield conn


def get_conn_sala_espera():
    """Solo para GET /sala-espera (público): el rol interno no puede leer datos personales."""
    with psycopg.connect(_database_url()) as conn:
        set_rls_context(conn, ROL_SALA_ESPERA)
        yield conn