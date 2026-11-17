"""Pruebas de RLS contra la base real, conectando como `meditriage_app` (S09-2).

Cada prueba siembra datos como enfermero DENTRO de una transacción y la revierte al final:
no queda nada en la base. Se omiten si no hay DATABASE_URL.
"""
import os
import uuid

import psycopg
import pytest

from app.db import ROL_AUTENTICACION, set_rls_context

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requiere DATABASE_URL (usuario meditriage_app)"
)

ENFERMERO_ID = uuid.UUID("a1111111-1111-4111-8111-111111111111")

# Tablas que se siembran y, por rol, cuáles deben verse (según docs/data/politicas_rls.md).
TABLAS = [
    "paciente",
    "consentimiento",
    "episodio_triage",
    "signos_vitales",
    "sintomas_triage",
    "clasificacion_ia",
    "decision_clinica",
]
VISIBLE = {
    "enfermero": set(TABLAS),
    "medico": set(TABLAS),
    "auditor": {"consentimiento", "clasificacion_ia", "decision_clinica"},
    "sin_rol": set(),
    "rol_inventado": set(),
}


@pytest.fixture
def conn():
    c = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        yield c
    finally:
        c.rollback()  # nada de lo sembrado se guarda
        c.close()


def _como(conn, rol, usuario_id=None):
    set_rls_context(conn, rol, usuario_id)


def _contar(conn, tabla):
    return conn.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]


@pytest.fixture
def sembrado(conn):
    """Crea una fila en cada tabla de triage como enfermero. Devuelve los ids."""
    _como(conn, "enfermero", ENFERMERO_ID)
    paciente, episodio = uuid.uuid4(), uuid.uuid4()
    conn.execute(
        "INSERT INTO paciente (paciente_id, nombre_completo, rut_hash) VALUES (%s, %s, %s)",
        (paciente, "Paciente Prueba RLS", uuid.uuid4().hex * 2),
    )
    conn.execute(
        """INSERT INTO consentimiento (consentimiento_id, paciente_id, otorgado, fecha_hora,
               tipo_consentimiento, version_texto)
           VALUES (%s, %s, TRUE, now(), 'tratamiento', '1.0')""",
        (uuid.uuid4(), paciente),
    )
    conn.execute(
        "INSERT INTO episodio_triage (episodio_id, paciente_id, estado) VALUES (%s, %s, 'en_espera')",
        (episodio, paciente),
    )
    conn.execute(
        """INSERT INTO signos_vitales (signos_vitales_id, episodio_id, presion_sistolica,
               presion_diastolica, frecuencia_cardiaca, frecuencia_respiratoria, temperatura,
               saturacion_oxigeno, escala_dolor, nivel_conciencia)
           VALUES (%s, %s, 120, 80, 80, 16, 36.5, 98, 3, 'alerta')""",
        (uuid.uuid4(), episodio),
    )
    conn.execute(
        """INSERT INTO sintomas_triage (sintoma_id, episodio_id, codigo_sintoma, severidad)
           VALUES (%s, %s, 'dolor_cabeza', 'leve')""",
        (uuid.uuid4(), episodio),
    )
    conn.execute(
        """INSERT INTO clasificacion_ia (clasificacion_id, episodio_id, token_correlacion_efimero,
               nivel_esi_sugerido, tiempo_solicitud, modelo_usado, hash_datos_enviados_ia)
           VALUES (%s, %s, %s, 3, now(), 'prueba', 'hash')""",
        (uuid.uuid4(), episodio, uuid.uuid4()),
    )
    conn.execute(
        """INSERT INTO decision_clinica (decision_id, episodio_id, nivel_esi_final,
               fecha_hora_decision, coincide_con_ia)
           VALUES (%s, %s, 3, now(), TRUE)""",
        (uuid.uuid4(), episodio),
    )
    return {"paciente": paciente, "episodio": episodio}


# --- Lectura: cada rol ve solo lo que le corresponde ---------------------------------------


@pytest.mark.parametrize("rol", list(VISIBLE))
@pytest.mark.parametrize("tabla", TABLAS)
def test_lectura_por_rol(conn, sembrado, rol, tabla):
    _como(conn, "" if rol == "sin_rol" else rol, ENFERMERO_ID)
    filas = _contar(conn, tabla)
    if tabla in VISIBLE[rol]:
        assert filas >= 1, f"{rol} debería ver {tabla}"
    else:
        assert filas == 0, f"{rol} no debería ver {tabla}"


# --- Escritura -------------------------------------------------------------------------------


def _bloqueado(conn, sql, params=()):
    """True si el SQL falla por permisos o no afecta filas (RLS lo oculta)."""
    try:
        with conn.transaction():  # savepoint: un error no aborta el resto de la prueba
            return conn.execute(sql, params).rowcount == 0
    except psycopg.errors.InsufficientPrivilege:
        return True


@pytest.mark.parametrize("rol", ["medico", "auditor"])
def test_medico_y_auditor_no_crean_episodios(conn, sembrado, rol):
    _como(conn, rol, uuid.uuid4())
    assert _bloqueado(
        conn,
        "INSERT INTO episodio_triage (episodio_id, paciente_id, estado) VALUES (%s, %s, 'en_espera')",
        (uuid.uuid4(), sembrado["paciente"]),
    )


def test_auditor_no_registra_decisiones(conn, sembrado):
    _como(conn, "auditor", uuid.uuid4())
    assert _bloqueado(
        conn,
        """INSERT INTO decision_clinica (decision_id, episodio_id, nivel_esi_final,
               fecha_hora_decision, coincide_con_ia) VALUES (%s, %s, 2, now(), FALSE)""",
        (uuid.uuid4(), sembrado["episodio"]),
    )


def test_medico_no_modifica_pacientes(conn, sembrado):
    _como(conn, "medico", uuid.uuid4())
    assert _bloqueado(conn, "UPDATE paciente SET nombre_completo = 'x'")


@pytest.mark.parametrize("rol", ["enfermero", "medico", "auditor"])
@pytest.mark.parametrize("tabla", TABLAS)
def test_nadie_borra(conn, sembrado, rol, tabla):
    _como(conn, rol, ENFERMERO_ID)
    assert _bloqueado(conn, f"DELETE FROM {tabla}")


def test_consentimiento_no_se_modifica(conn, sembrado):
    _como(conn, "enfermero", ENFERMERO_ID)
    assert _bloqueado(conn, "UPDATE consentimiento SET otorgado = FALSE")


# --- usuario_staff: login y fila propia ----------------------------------------------------


def test_login_lee_usuarios_y_los_roles_solo_su_fila(conn):
    _como(conn, ROL_AUTENTICACION)
    assert _contar(conn, "usuario_staff") >= 1  # usuarios de demostración (migración 0005)

    _como(conn, "enfermero", uuid.uuid4())  # id que no existe: no ve ninguna fila
    assert _contar(conn, "usuario_staff") == 0

    _como(conn, "enfermero", ENFERMERO_ID)  # el enfermero de demostración ve solo la suya
    assert _contar(conn, "usuario_staff") <= 1