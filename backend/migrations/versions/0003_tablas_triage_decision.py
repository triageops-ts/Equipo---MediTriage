
"""crear tablas de triage y decision clinica

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Personal clínico.
    # La autenticación puede delegarse a Keycloak.
    op.create_table(
        "usuario_staff",
        sa.Column(
            "usuario_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rol", sa.String(), nullable=False),
        sa.Column(
            "activo",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("nombre_completo", sa.String(), nullable=True),
        sa.Column("rut", sa.LargeBinary(), nullable=True),
        sa.Column("email", sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint("usuario_id"),
    )

    # 2. Episodio de triage.
    # usuario_id queda nullable mientras el login no sea obligatorio.
    op.create_table(
        "episodio_triage",
        sa.Column(
            "episodio_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("paciente_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column(
            "fecha_hora_ingreso",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "motivo_consulta_texto_libre",
            sa.Text(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["paciente.paciente_id"],
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario_staff.usuario_id"],
        ),
        sa.PrimaryKeyConstraint("episodio_id"),
    )

    # 3. Signos vitales asociados al episodio.
    op.create_table(
        "signos_vitales",
        sa.Column(
            "signos_vitales_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("episodio_id", sa.UUID(), nullable=False),
        sa.Column("presion_sistolica", sa.Integer(), nullable=False),
        sa.Column("presion_diastolica", sa.Integer(), nullable=False),
        sa.Column("frecuencia_cardiaca", sa.Integer(), nullable=False),
        sa.Column("frecuencia_respiratoria", sa.Integer(), nullable=False),
        sa.Column("temperatura", sa.Float(), nullable=False),
        sa.Column("saturacion_oxigeno", sa.Float(), nullable=False),
        sa.Column("escala_dolor", sa.Integer(), nullable=False),
        sa.Column("nivel_conciencia", sa.String(), nullable=False),
        sa.Column(
            "fecha_hora_medicion",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "presion_sistolica BETWEEN 40 AND 260",
            name="ck_signos_presion_sistolica",
        ),
        sa.CheckConstraint(
            "presion_diastolica BETWEEN 20 AND 200",
            name="ck_signos_presion_diastolica",
        ),
        sa.CheckConstraint(
            "presion_diastolica < presion_sistolica",
            name="ck_signos_presion_coherente",
        ),
        sa.CheckConstraint(
            "frecuencia_cardiaca BETWEEN 20 AND 300",
            name="ck_signos_frecuencia_cardiaca",
        ),
        sa.CheckConstraint(
            "frecuencia_respiratoria BETWEEN 5 AND 80",
            name="ck_signos_frecuencia_respiratoria",
        ),
        sa.CheckConstraint(
            "temperatura BETWEEN 30 AND 43",
            name="ck_signos_temperatura",
        ),
        sa.CheckConstraint(
            "saturacion_oxigeno BETWEEN 0 AND 100",
            name="ck_signos_saturacion",
        ),
        sa.CheckConstraint(
            "escala_dolor BETWEEN 0 AND 10",
            name="ck_signos_escala_dolor",
        ),
        sa.CheckConstraint(
            "nivel_conciencia IN ('alerta', 'verbal', 'dolor', 'inconsciente')",
            name="ck_signos_nivel_conciencia",
        ),
        sa.ForeignKeyConstraint(
            ["episodio_id"],
            ["episodio_triage.episodio_id"],
        ),
        sa.PrimaryKeyConstraint("signos_vitales_id"),
    )

    # 4. Resultado de clasificación de IA.
    op.create_table(
        "clasificacion_ia",
        sa.Column(
            "clasificacion_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("episodio_id", sa.UUID(), nullable=False),
        sa.Column("token_correlacion_efimero", sa.UUID(), nullable=False),
        sa.Column("nivel_esi_sugerido", sa.Integer(), nullable=False),
        sa.Column(
            "tiempo_solicitud",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "tiempo_respuesta",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column("modelo_usado", sa.String(), nullable=False),
        sa.Column("hash_datos_enviados_ia", sa.String(), nullable=False),
        sa.Column("justificacion_ia", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "nivel_esi_sugerido BETWEEN 1 AND 5",
            name="ck_clasificacion_ia_esi",
        ),
        sa.ForeignKeyConstraint(
            ["episodio_id"],
            ["episodio_triage.episodio_id"],
        ),
        sa.PrimaryKeyConstraint("clasificacion_id"),
    )

    # 5. Decisión clínica final.
    # Una sola decisión por episodio.
    op.create_table(
        "decision_clinica",
        sa.Column(
            "decision_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("episodio_id", sa.UUID(), nullable=False),
        sa.Column("nivel_esi_final", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("fecha_hora_decision", sa.DateTime(), nullable=False),
        sa.Column("coincide_con_ia", sa.Boolean(), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "nivel_esi_final BETWEEN 1 AND 5",
            name="ck_decision_clinica_esi",
        ),
        sa.ForeignKeyConstraint(
            ["episodio_id"],
            ["episodio_triage.episodio_id"],
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario_staff.usuario_id"],
        ),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "episodio_id",
            name="uq_decision_clinica_episodio",
        ),
    )

    # Índices para consultas habituales.
    op.create_index(
        "ix_episodio_triage_paciente_id",
        "episodio_triage",
        ["paciente_id"],
    )
    op.create_index(
        "ix_episodio_triage_usuario_id",
        "episodio_triage",
        ["usuario_id"],
    )
    op.create_index(
        "ix_signos_vitales_episodio_id",
        "signos_vitales",
        ["episodio_id"],
    )
    op.create_index(
        "ix_clasificacion_ia_episodio_tiempo",
        "clasificacion_ia",
        ["episodio_id", "tiempo_respuesta"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clasificacion_ia_episodio_tiempo",
        table_name="clasificacion_ia",
    )
    op.drop_index(
        "ix_signos_vitales_episodio_id",
        table_name="signos_vitales",
    )
    op.drop_index(
        "ix_episodio_triage_usuario_id",
        table_name="episodio_triage",
    )
    op.drop_index(
        "ix_episodio_triage_paciente_id",
        table_name="episodio_triage",
    )

    op.drop_table("decision_clinica")
    op.drop_table("clasificacion_ia")
    op.drop_table("signos_vitales")
    op.drop_table("episodio_triage")
    op.drop_table("usuario_staff")
