"""Registro persistente de fallos al guardar decisiones clínicas.

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preservar una tabla legacy incompatible que puede existir
    # en bases de datos anteriores a esta migración.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("registro_auditoria", schema="public"):
        columnas = {
            columna["name"]
            for columna in inspector.get_columns(
                "registro_auditoria",
                schema="public",
            )
        }

        columnas_nuevas = {
            "episodio_id",
            "decision_id",
            "usuario_id_actor",
            "sugerencia_ia",
            "prompt_enviado",
            "decision_final",
            "hay_discrepancia",
        }

        if not columnas_nuevas.issubset(columnas):
            if inspector.has_table(
                "registro_auditoria_legacy",
                schema="public",
            ):
                raise RuntimeError(
                    "Ya existe registro_auditoria_legacy; "
                    "se cancela para evitar sobrescribir datos."
                )

            op.execute(
                "ALTER TABLE public.registro_auditoria "
                "RENAME TO registro_auditoria_legacy"
            )
            op.execute(
                "ALTER TABLE public.registro_auditoria_legacy "
                "RENAME CONSTRAINT registro_auditoria_pkey "
                "TO registro_auditoria_legacy_pkey"
            )

    op.create_table(
        "registro_auditoria",
        sa.Column("registro_id", sa.UUID(), nullable=False),
        sa.Column("episodio_id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=True),
        sa.Column("evento_tipo", sa.String(100), nullable=False),
        sa.Column("usuario_id_actor", sa.UUID(), nullable=False),
        sa.Column("sugerencia_ia", sa.Integer(), nullable=True),
        sa.Column("prompt_enviado", sa.Text(), nullable=True),
        sa.Column("decision_final", sa.Integer(), nullable=True),
        sa.Column("hay_discrepancia", sa.Boolean(), nullable=False),
        sa.Column("hash_anterior", sa.String(64), nullable=False),
        sa.Column("hash_actual", sa.String(64), nullable=False),
        sa.Column(
            "fecha_hora_evento",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'UTC')"),
        ),
        sa.ForeignKeyConstraint(
            ["episodio_id"], ["episodio_triage.episodio_id"]
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"], ["decision_clinica.decision_id"]
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id_actor"], ["usuario_staff.usuario_id"]
        ),
        sa.PrimaryKeyConstraint("registro_id"),
    )

    op.create_index(
        "ix_registro_auditoria_episodio_fecha",
        "registro_auditoria",
        ["episodio_id", "fecha_hora_evento"],
    )

    op.execute(
        "GRANT SELECT, INSERT ON registro_auditoria TO meditriage_app"
    )
    op.execute("ALTER TABLE registro_auditoria ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE registro_auditoria FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY registro_auditoria_insert
        ON registro_auditoria
        FOR INSERT TO meditriage_app
        WITH CHECK (
            app_rol() = 'enfermero'
            AND usuario_id_actor = app_usuario_id()
        )
    """)
    op.execute("""
        CREATE POLICY registro_auditoria_select
        ON registro_auditoria
        FOR SELECT TO meditriage_app
        USING (app_rol() IN ('auditor', 'enfermero'))
    """)


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS registro_auditoria_select ON registro_auditoria"
    )
    op.execute(
        "DROP POLICY IF EXISTS registro_auditoria_insert ON registro_auditoria"
    )
    op.drop_index(
        "ix_registro_auditoria_episodio_fecha",
        table_name="registro_auditoria",
    )
    op.drop_table("registro_auditoria")
