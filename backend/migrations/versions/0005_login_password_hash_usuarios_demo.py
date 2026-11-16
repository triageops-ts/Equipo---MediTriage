"""login: password_hash en usuario_staff y 3 usuarios de demostración

Tarjeta S09-1.

- Agrega `password_hash` (bcrypt) a usuario_staff. Es NULL en los usuarios que ya existían:
  hasta que se les asigne una contraseña, esos usuarios no pueden iniciar sesión.
- Crea 3 usuarios de DEMOSTRACIÓN con datos sintéticos (enfermero, médico, auditor).
  La contraseña de demo sale de DEMO_PASSWORD (por defecto "Demo-2026!") y solo se guarda
  su hash. NO usar estos usuarios ni esta contraseña en producción.
- El correo se guarda cifrado (pgcrypto) con APP_ENCRYPTION_KEY, igual que en el resto de
  la base; por eso esta migración necesita esa variable de entorno.

Revision ID: 0005
Revises: 0004
"""
import os
from typing import Sequence, Union

import bcrypt
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PASSWORD_DEMO_POR_DEFECTO = "Demo-2026!"

# (usuario_id fijo, rol, nombre sintético, correo sintético)
USUARIOS_DEMO = [
    ("a1111111-1111-4111-8111-111111111111", "enfermero", "Camila Rojas (demo)", "enfermero@meditriage.test"),
    ("b2222222-2222-4222-8222-222222222222", "medico", "Andrés Fuentes (demo)", "medico@meditriage.test"),
    ("c3333333-3333-4333-8333-333333333333", "auditor", "Valentina Soto (demo)", "auditor@meditriage.test"),
]


def upgrade() -> None:
    clave = os.environ.get("APP_ENCRYPTION_KEY")
    if not clave:
        raise RuntimeError("Falta la variable de entorno APP_ENCRYPTION_KEY.")
    # Contraseña de demostración pública (usuarios con datos sintéticos). No es una credencial real.
    password = os.environ.get("DEMO_PASSWORD", PASSWORD_DEMO_POR_DEFECTO)  # nosemgrep: semgrep.meditriage-secreto-en-codigo
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column("usuario_staff", sa.Column("password_hash", sa.String(), nullable=True))

    insertar = sa.text(
        """
        INSERT INTO usuario_staff (usuario_id, rol, activo, nombre_completo, email, password_hash)
        VALUES (
            CAST(:usuario_id AS uuid), :rol, true, :nombre,
            pgp_sym_encrypt(CAST(:email AS text), CAST(:clave AS text), 'cipher-algo=aes256'),
            :password_hash
        )
        ON CONFLICT (usuario_id) DO NOTHING
        """
    )
    for usuario_id, rol, nombre, email in USUARIOS_DEMO:
        op.get_bind().execute(
            insertar,
            {
                "usuario_id": usuario_id,
                "rol": rol,
                "nombre": nombre,
                "email": email,
                "clave": clave,
                "password_hash": password_hash,
            },
        )


def downgrade() -> None:
    # Borra los usuarios de demo solo si nadie los referencia (episodios o decisiones).
    ids = [u[0] for u in USUARIOS_DEMO]
    op.get_bind().execute(
        sa.text(
            """
            DELETE FROM usuario_staff u
            WHERE u.usuario_id = ANY(CAST(:ids AS uuid[]))
              AND NOT EXISTS (SELECT 1 FROM episodio_triage e WHERE e.usuario_id = u.usuario_id)
              AND NOT EXISTS (SELECT 1 FROM decision_clinica d WHERE d.usuario_id = u.usuario_id)
            """
        ),
        {"ids": ids},
    )
    op.drop_column("usuario_staff", "password_hash")
