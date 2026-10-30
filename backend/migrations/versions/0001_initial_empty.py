"""migración inicial vacía

Punto de partida del historial de migraciones. No cambia el esquema: solo
deja a Alembic funcionando (crea la tabla alembic_version).

Revision ID: 0001
Revises:
Create Date: 2026-10-30
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass