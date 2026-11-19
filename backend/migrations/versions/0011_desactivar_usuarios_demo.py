"""Desactivar las cuentas demo hasta que se ejecuten los seeds administrativos.

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels = None
depends_on = None

USUARIOS_DEMO = (
    "a1111111-1111-4111-8111-111111111111",
    "b2222222-2222-4222-8222-222222222222",
    "c3333333-3333-4333-8333-333333333333",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE usuario_staff
            SET activo = false
            WHERE usuario_id = ANY(CAST(:ids AS uuid[]))
            """
        ).bindparams(ids=list(USUARIOS_DEMO))
    )


def downgrade() -> None:
    # En la migración 0005 estas cuentas fueron creadas activas.
    op.execute(
        sa.text(
            """
            UPDATE usuario_staff
            SET activo = true
            WHERE usuario_id = ANY(CAST(:ids AS uuid[]))
            """
        ).bindparams(ids=list(USUARIOS_DEMO))
    )
