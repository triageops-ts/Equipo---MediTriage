"""Agregar síntomas estructurados al episodio de triage.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sintomas_triage",
        sa.Column(
            "sintoma_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("episodio_id", sa.UUID(), nullable=False),
        sa.Column("codigo_sintoma", sa.String(100), nullable=False),
        sa.Column("severidad", sa.String(20), nullable=False),
        sa.Column("tiempo_evolucion_horas", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["episodio_id"],
            ["episodio_triage.episodio_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "severidad IN ('leve', 'moderada', 'severa')",
            name="ck_sintomas_triage_severidad",
        ),
        sa.CheckConstraint(
            "tiempo_evolucion_horas IS NULL OR tiempo_evolucion_horas >= 0",
            name="ck_sintomas_triage_evolucion",
        ),
        sa.PrimaryKeyConstraint("sintoma_id"),
    )

    op.create_index(
        "ix_sintomas_triage_episodio_id",
        "sintomas_triage",
        ["episodio_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sintomas_triage_episodio_id",
        table_name="sintomas_triage",
    )
    op.drop_table("sintomas_triage")