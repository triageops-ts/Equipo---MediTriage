"""Agregar paciente.rut_hash (HMAC-SHA256 del RUT) con índice único.

Revision ID: 0007
Revises: 0006
"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    enc = os.environ.get("APP_ENCRYPTION_KEY")
    hk = os.environ.get("APP_RUT_HASH_KEY")
    if not enc or not hk:
        raise RuntimeError("Esta migración requiere APP_ENCRYPTION_KEY y APP_RUT_HASH_KEY.")

    op.add_column("paciente", sa.Column("rut_hash", sa.String(64), nullable=True))

    # Calcula el hash de los pacientes que ya existen. Si algún RUT no descifra
    # con la clave, esto falla y la migración se revierte completa.
    op.execute(
        sa.text(
            "UPDATE paciente SET rut_hash = encode(hmac("
            "pgp_sym_decrypt(rut, CAST(:enc AS text)), CAST(:hk AS text), 'sha256'), 'hex') "
            "WHERE rut IS NOT NULL"
        ).bindparams(enc=enc, hk=hk)
    )

    # Si hubiera un RUT repetido, aquí falla: mejor enterarse ahora.
    op.create_index("uq_paciente_rut_hash", "paciente", ["rut_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_paciente_rut_hash", table_name="paciente")
    op.drop_column("paciente", "rut_hash")