"""Entorno de Alembic: toma la conexión desde la variable DATABASE_URL."""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Aún no hay modelos de SQLAlchemy: las migraciones se escriben a mano.
# Cuando existan, se asigna aquí su MetaData para usar --autogenerate.
target_metadata = None


def get_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta la variable de entorno DATABASE_URL.")

    # Protección: la base de Neon es compartida y sus tablas se crearon fuera de
    # Alembic. Para migrar contra ella hay que pedirlo de forma explícita.
    host = make_url(url).host or ""
    if host.endswith("neon.tech") and os.environ.get("ALEMBIC_ALLOW_REMOTE") != "1":
        raise RuntimeError(
            f"DATABASE_URL apunta a una base remota ({host}). Para migrarla de "
            "verdad define ALEMBIC_ALLOW_REMOTE=1; para pruebas usa el Postgres "
            "local de docker-compose."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()