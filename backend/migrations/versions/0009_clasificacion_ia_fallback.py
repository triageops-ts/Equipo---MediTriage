"""clasificacion_ia: fallback_aplicado e idempotency_key (S09-7).

- fallback_aplicado: true si la sugerencia salió del árbol de reglas de respaldo
  (la IA falló o pasó de 1500 ms). Las filas que ya existían quedan en false.
- idempotency_key: clave opcional del header Idempotency-Key. Un reintento con la misma
  clave sobre el mismo episodio devuelve la clasificación ya guardada en vez de llamar
  otra vez a la IA. Es única por episodio; las filas sin clave no se ven afectadas.

Los GRANTs y las políticas RLS de la 0008 son por tabla, así que cubren las columnas nuevas.

Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clasificacion_ia",
        sa.Column(
            "fallback_aplicado",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "clasificacion_ia",
        sa.Column("idempotency_key", sa.UUID(), nullable=True),
    )
    op.create_index(
        "uq_clasificacion_ia_episodio_idempotency_key",
        "clasificacion_ia",
        ["episodio_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_clasificacion_ia_episodio_idempotency_key",
        table_name="clasificacion_ia",
    )
    op.drop_column("clasificacion_ia", "idempotency_key")
    op.drop_column("clasificacion_ia", "fallback_aplicado")
