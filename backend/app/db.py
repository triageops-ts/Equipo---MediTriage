import os

import psycopg


def encryption_key() -> str:
    key = os.environ.get("APP_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("Falta la variable de entorno APP_ENCRYPTION_KEY.")
    return key


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta la variable de entorno DATABASE_URL.")
    with psycopg.connect(url) as conn:
        yield conn