"""Tabla canario para verificar la clave de cifrado al arrancar.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clave_canario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("valor", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_clave_canario_unica"),
    )
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meditriage_app') THEN
            GRANT SELECT, INSERT ON clave_canario TO meditriage_app;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("clave_canario")