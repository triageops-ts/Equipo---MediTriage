import psycopg

from app.db import encryption_key

_TEXTO = "meditriage-canario-v1"
_MENSAJE = "APP_ENCRYPTION_KEY no coincide con la clave con la que se cifró la base."


def _descifra(conn: psycopg.Connection, valor: bytes, key: str) -> str | None:
    try:
        with conn.transaction():  # savepoint: un fallo no aborta la transacción
            return conn.execute(
                "SELECT pgp_sym_decrypt(%s::bytea, %s::text)", (valor, key)
            ).fetchone()[0]
    except psycopg.Error:
        return None


def verificar_clave_cifrado(conn: psycopg.Connection) -> None:
    """Lanza RuntimeError si la clave actual no corresponde a los datos cifrados."""
    key = encryption_key()
    try:
        fila = conn.execute("SELECT valor FROM clave_canario WHERE id = 1").fetchone()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        raise RuntimeError("Falta la tabla clave_canario: ejecuta `alembic upgrade head`.") from None

    if fila is not None:
        if _descifra(conn, fila[0], key) != _TEXTO:
            raise RuntimeError(_MENSAJE)
    else:
        # Primera vez en esta base: si ya hay pacientes, la clave debe descifrar
        # al menos uno antes de sembrar el canario (si no, no detectaría nada).
        existente = conn.execute(
            "SELECT rut FROM paciente WHERE rut IS NOT NULL LIMIT 1"
        ).fetchone()
        if existente is not None and _descifra(conn, existente[0], key) is None:
            raise RuntimeError(_MENSAJE)
        conn.execute(
            "INSERT INTO clave_canario (id, valor) "
            "VALUES (1, pgp_sym_encrypt(%s::text, %s::text, 'cipher-algo=aes256')) "
            "ON CONFLICT (id) DO NOTHING",  # por si dos réplicas arrancan a la vez
            (_TEXTO, key),
        )
    conn.commit()