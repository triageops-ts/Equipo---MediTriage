"""RLS para la pantalla pública de la sala de espera (S11-10, US-04).

GET /sala-espera no tiene token, así que el backend fija `app.rol = 'sala_espera'`
(app/db.py: get_conn_sala_espera). Este contexto solo puede LEER las tres tablas que
necesita para ordenar la fila:

- episodio_triage   (estado y hora de ingreso)
- clasificacion_ia  (nivel sugerido por la IA)
- decision_clinica  (nivel final)

No recibe permisos sobre paciente, contacto_paciente, contacto_emergencia,
consentimiento, usuario_staff, signos_vitales, sintomas_triage ni registro_auditoria:
con app.rol = 'sala_espera' esas tablas devuelven cero filas.

Las políticas nuevas son PERMISSIVE y se suman (OR) a las de la 0008, que no se tocan.

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "meditriage_app"
CONTEXTO = "sala_espera"
TABLAS = ("episodio_triage", "clasificacion_ia", "decision_clinica")


def upgrade() -> None:
    for t in TABLAS:
        op.execute(f"DROP POLICY IF EXISTS {t}_select_sala_espera ON {t}")
        op.execute(
            f"CREATE POLICY {t}_select_sala_espera ON {t} FOR SELECT TO {APP_ROLE} "
            f"USING (app_rol() = '{CONTEXTO}')"
        )


def downgrade() -> None:
    for t in TABLAS:
        op.execute(f"DROP POLICY IF EXISTS {t}_select_sala_espera ON {t}")
