"""paciente y consentimiento: tablas, restricciones y Row-Level Security

Tarjeta S04-2.

- Si las tablas NO existen (Postgres local de docker-compose): las crea. El bloque
  create_table fue generado con `alembic revision --autogenerate` a partir de models.py.
- Si YA existen (la base de Neon, creada fuera de Alembic): no las toca; solo agrega
  NOT NULL a los campos obligatorios. Si alguna fila tiene NULL ahí, la migración falla
  y se revierte completa (el DDL de Postgres es transaccional).
- En ambos casos: crea el rol de la app (meditriage_app, sin BYPASSRLS), le da permisos
  mínimos y activa RLS con políticas por rol (enfermero, medico, auditor).

El rol sale de la variable de sesión `app.rol`, que el backend fija en cada transacción
(ver db.py). Sin rol, o con un rol desconocido, las políticas no dejan pasar nada.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "meditriage_app"

# Campos que deben ser obligatorios (tabla -> columnas). Solo se aplican si la tabla ya existía.
NOT_NULL = {
    "consentimiento": [
        "paciente_id",
        "tipo_consentimiento",
        "otorgado",
        "fecha_hora",
        "version_texto",
    ],
    "contacto_emergencia": ["paciente_id"],
}

RLS_TABLES = ["paciente", "consentimiento", "contacto_paciente", "contacto_emergencia"]


def _create_tables() -> None:
    op.create_table(
        "paciente",
        sa.Column("paciente_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nombre_completo", sa.String(), nullable=True),
        sa.Column("rut", sa.LargeBinary(), nullable=True),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column("sexo_biologico", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("paciente_id"),
    )
    op.create_table(
        "consentimiento",
        sa.Column("consentimiento_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("paciente_id", sa.UUID(), nullable=False),
        sa.Column("tipo_consentimiento", sa.String(), nullable=False),
        sa.Column("otorgado", sa.Boolean(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("firma_digital", sa.LargeBinary(), nullable=True),
        sa.Column("version_texto", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.paciente_id"]),
        sa.PrimaryKeyConstraint("consentimiento_id"),
    )
    op.create_table(
        "contacto_emergencia",
        sa.Column("contacto_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("paciente_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("relacion", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.paciente_id"]),
        sa.PrimaryKeyConstraint("contacto_id"),
    )
    op.create_table(
        "contacto_paciente",
        sa.Column("paciente_id", sa.UUID(), nullable=False),
        sa.Column("direccion", sa.LargeBinary(), nullable=True),
        sa.Column("telefono", sa.LargeBinary(), nullable=True),
        sa.Column("email", sa.LargeBinary(), nullable=True),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.paciente_id"]),
        sa.PrimaryKeyConstraint("paciente_id"),
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # 1) Tablas: crear las que falten; en las que ya existen, solo exigir los NOT NULL.
    if not inspector.has_table("paciente"):
        _create_tables()
    else:
        for tabla, columnas in NOT_NULL.items():
            for columna in columnas:
                op.alter_column(tabla, columna, nullable=False)

    # 2) Rol de la aplicación. NOLOGIN a propósito: la contraseña NO va en el repo.
    #    Después de migrar, quien administre la base ejecuta una sola vez (fuera del repo):
    #    ALTER ROLE meditriage_app WITH LOGIN PASSWORD '<contraseña>';
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")

    # 3) Función auxiliar: rol de negocio de la transacción actual (NULL si no se fijó).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_rol() RETURNS text
        LANGUAGE sql STABLE AS
        $$ SELECT NULLIF(current_setting('app.rol', true), '') $$;
        """
    )

    # 4) Permisos mínimos. Nadie borra: los registros clínicos no se eliminan.
    #    consentimiento es append-only (sin UPDATE): revocar = insertar otra fila.
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON paciente TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON consentimiento TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON contacto_paciente TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON contacto_emergencia TO {APP_ROLE}")

    # 5) Activar RLS (FORCE también aplica al dueño de la tabla si no tiene BYPASSRLS).
    for tabla in RLS_TABLES:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")

    # 6) Políticas por rol.
    #    paciente / contacto_*: enfermero lee y escribe; médico solo lee; auditor sin acceso.
    for tabla in ("paciente", "contacto_paciente", "contacto_emergencia"):
        op.execute(
            f"""CREATE POLICY {tabla}_select ON {tabla} FOR SELECT TO {APP_ROLE}
                USING (app_rol() IN ('enfermero', 'medico'))"""
        )
        op.execute(
            f"""CREATE POLICY {tabla}_insert ON {tabla} FOR INSERT TO {APP_ROLE}
                WITH CHECK (app_rol() = 'enfermero')"""
        )
        op.execute(
            f"""CREATE POLICY {tabla}_update ON {tabla} FOR UPDATE TO {APP_ROLE}
                USING (app_rol() = 'enfermero') WITH CHECK (app_rol() = 'enfermero')"""
        )

    #    consentimiento: los tres roles leen (el auditor verifica consentimientos);
    #    solo el enfermero registra; nadie modifica ni borra.
    op.execute(
        f"""CREATE POLICY consentimiento_select ON consentimiento FOR SELECT TO {APP_ROLE}
            USING (app_rol() IN ('enfermero', 'medico', 'auditor'))"""
    )
    op.execute(
        f"""CREATE POLICY consentimiento_insert ON consentimiento FOR INSERT TO {APP_ROLE}
            WITH CHECK (app_rol() = 'enfermero')"""
    )


def downgrade() -> None:
    # Revierte solo seguridad y restricciones. NO borra tablas: en Neon ya existían
    # antes de esta migración y contienen (o contendrán) datos clínicos.
    for tabla in RLS_TABLES:
        for politica in ("select", "insert", "update"):
            op.execute(f"DROP POLICY IF EXISTS {tabla}_{politica} ON {tabla}")
        op.execute(f"ALTER TABLE {tabla} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {tabla} FROM {APP_ROLE}")

    op.execute("DROP FUNCTION IF EXISTS app_rol()")

    for tabla, columnas in NOT_NULL.items():
        for columna in columnas:
            op.alter_column(tabla, columna, nullable=True)
    # El rol meditriage_app se deja creado a propósito (puede tener login y conexiones activas).
