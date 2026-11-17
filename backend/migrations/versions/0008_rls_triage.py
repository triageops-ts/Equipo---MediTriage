"""RLS en tablas de triage y GRANTs mínimos (S09-2).

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "meditriage_app"
TABLAS = ["usuario_staff", "episodio_triage", "signos_vitales",
          "sintomas_triage", "clasificacion_ia", "decision_clinica"]
TABLAS_BASE = ["paciente", "consentimiento", "contacto_paciente", "contacto_emergencia"]


def _pol(nombre, tabla, accion, expr, check=False):
    clausula = "WITH CHECK" if check else "USING"
    op.execute(f"CREATE POLICY {nombre} ON {tabla} FOR {accion} TO {APP_ROLE} {clausula} ({expr})")


def upgrade() -> None:
    # --- Base autosuficiente (idempotente): rol, función y RLS de las tablas de la 0002 ---
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
    op.execute(
        """CREATE OR REPLACE FUNCTION app_rol() RETURNS text
           LANGUAGE sql STABLE AS
           $$ SELECT NULLIF(current_setting('app.rol', true), '') $$;"""
    )

    # Permisos de paciente, contactos, consentimiento y clave_canario (0002 y 0006).
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON paciente, contacto_paciente, contacto_emergencia TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON consentimiento, clave_canario TO {APP_ROLE}")

    for t in TABLAS_BASE:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        for accion in ("select", "insert", "update"):
            op.execute(f"DROP POLICY IF EXISTS {t}_{accion} ON {t}")

    for t in ("paciente", "contacto_paciente", "contacto_emergencia"):
        _pol(f"{t}_select", t, "SELECT", "app_rol() IN ('enfermero','medico')")
        _pol(f"{t}_insert", t, "INSERT", "app_rol() = 'enfermero'", check=True)
        _pol(f"{t}_update", t, "UPDATE", "app_rol() = 'enfermero'")
    _pol("consentimiento_select", "consentimiento", "SELECT",
         "app_rol() IN ('enfermero','medico','auditor')")
    _pol("consentimiento_insert", "consentimiento", "INSERT",
         "app_rol() = 'enfermero'", check=True)

    # --- Tablas de triage (S09-2) ---
    op.execute(
        """CREATE OR REPLACE FUNCTION app_usuario_id() RETURNS uuid
           LANGUAGE sql STABLE AS
           $$ SELECT NULLIF(current_setting('app.usuario_id', true), '')::uuid $$;"""
    )

    # GRANTs mínimos: sin DELETE para nadie.
    op.execute(f"GRANT SELECT ON usuario_staff TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON episodio_triage TO {APP_ROLE}")  # UPDATE: FOR UPDATE
    op.execute(f"GRANT SELECT, INSERT ON signos_vitales, sintomas_triage, "
               f"clasificacion_ia, decision_clinica TO {APP_ROLE}")

    for t in TABLAS:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")

    # usuario_staff: login (contexto interno) y cada usuario ve solo su fila.
    _pol("usuario_staff_select", "usuario_staff", "SELECT",
         "app_rol() = 'autenticacion' OR (app_rol() IN ('enfermero','medico','auditor') "
         "AND usuario_id = app_usuario_id())")

    # episodio, signos, síntomas: enfermero escribe; médico lee; auditor nada.
    for t in ("episodio_triage", "signos_vitales", "sintomas_triage"):
        _pol(f"{t}_select", t, "SELECT", "app_rol() IN ('enfermero','medico')")
        _pol(f"{t}_insert", t, "INSERT", "app_rol() = 'enfermero'", check=True)
    _pol("episodio_triage_update", "episodio_triage", "UPDATE", "app_rol() = 'enfermero'")

    # clasificacion_ia y decision_clinica: enfermero escribe; médico y auditor leen.
    for t in ("clasificacion_ia", "decision_clinica"):
        _pol(f"{t}_select", t, "SELECT", "app_rol() IN ('enfermero','medico','auditor')")
        _pol(f"{t}_insert", t, "INSERT", "app_rol() = 'enfermero'", check=True)


def downgrade() -> None:
    for t in TABLAS + TABLAS_BASE:
        for accion in ("select", "insert", "update"):
            op.execute(f"DROP POLICY IF EXISTS {t}_{accion} ON {t}")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {t} FROM {APP_ROLE}")
    op.execute("DROP FUNCTION IF EXISTS app_usuario_id()")
    # app_rol() y el rol se dejan: los usa también la migración 0002.