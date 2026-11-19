"""Comandos administrativos puntuales para MediTriage.

Uso:
    python -m app.cli seed-roles
    python -m app.cli seed-demo

Los seeds requieren una conexión privilegiada en SEED_DATABASE_URL.
No usar cuentas demo en producción.
"""
import argparse
import os
import sys
from datetime import date
from uuid import UUID

import psycopg

from app.core.consent import CONSENT_TIPO, CONSENT_VERSION_ACTUAL
from app.core.rut import calcular_dv, formatear_rut, normalizar_rut
from app.core.rut_hash import calcular_rut_hash
from app.core.security import hash_password


USUARIOS_DEMO = (
    (
        "a1111111-1111-4111-8111-111111111111",
        "enfermero",
        "Camila Rojas (demo)",
        "enfermero@meditriage.test",
    ),
    (
        "b2222222-2222-4222-8222-222222222222",
        "medico",
        "Andrés Fuentes (demo)",
        "medico@meditriage.test",
    ),
    (
        "c3333333-3333-4333-8333-333333333333",
        "auditor",
        "Valentina Soto (demo)",
        "auditor@meditriage.test",
    ),
)

PACIENTES_DEMO = (
    {
        "id": "d1111111-1111-4111-8111-111111111111",
        "rut_cuerpo": "11111111",
        "nombre": "Paciente Demo Uno",
        "nacimiento": date(1990, 1, 15),
        "sexo": "masculino",
        "direccion": "Dirección ficticia 101",
        "telefono": "+56900000001",
        "email": "paciente1@meditriage.test",
        "consentimiento_id": "e1111111-1111-4111-8111-111111111111",
    },
    {
        "id": "d2222222-2222-4222-8222-222222222222",
        "rut_cuerpo": "22222222",
        "nombre": "Paciente Demo Dos",
        "nacimiento": date(1985, 6, 20),
        "sexo": "femenino",
        "direccion": "Dirección ficticia 202",
        "telefono": "+56900000002",
        "email": "paciente2@meditriage.test",
        "consentimiento_id": "e2222222-2222-4222-8222-222222222222",
    },
)


def _configuracion() -> tuple[str, str]:
    database_url = os.environ.get("SEED_DATABASE_URL")
    encryption_key = os.environ.get("APP_ENCRYPTION_KEY")

    if not database_url:
        raise RuntimeError("Falta SEED_DATABASE_URL (conexión privilegiada de la base).")
    if not encryption_key:
        raise RuntimeError("Falta APP_ENCRYPTION_KEY.")

    return database_url, encryption_key


def seed_roles() -> None:
    database_url, encryption_key = _configuracion()
    password = os.environ.get("DEMO_PASSWORD")

    if not password:
        raise RuntimeError(
            "Define DEMO_PASSWORD explícitamente antes de crear o actualizar "
            "las cuentas demo."
        )
    if len(password.encode("utf-8")) > 72:
        raise RuntimeError("DEMO_PASSWORD supera el máximo de 72 bytes de bcrypt.")

    password_hash = hash_password(password)

    sql = """
        INSERT INTO usuario_staff (
            usuario_id, rol, activo, nombre_completo, email, password_hash
        )
        VALUES (
            %s::uuid, %s, true, %s,
            pgp_sym_encrypt(%s::text, %s::text, 'cipher-algo=aes256'),
            %s
        )
        ON CONFLICT (usuario_id) DO UPDATE SET
            rol = EXCLUDED.rol,
            activo = true,
            nombre_completo = EXCLUDED.nombre_completo,
            email = EXCLUDED.email,
            password_hash = EXCLUDED.password_hash
    """

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for usuario_id, rol, nombre, email in USUARIOS_DEMO:
                cur.execute(
                    sql,
                    (
                        usuario_id,
                        rol,
                        nombre,
                        email,
                        encryption_key,
                        password_hash,
                    ),
                )

    print("Seed de roles completado: 3 cuentas demo creadas o actualizadas.")


def seed_demo() -> None:
    database_url, encryption_key = _configuracion()
    hash_key = os.environ.get("APP_RUT_HASH_KEY")

    if not hash_key:
        raise RuntimeError("Falta APP_RUT_HASH_KEY.")

    sql_paciente = """
        INSERT INTO paciente (
            paciente_id, nombre_completo, rut, rut_hash,
            fecha_nacimiento, sexo_biologico
        )
        VALUES (
            %s::uuid, %s,
            pgp_sym_encrypt(%s::text, %s::text, 'cipher-algo=aes256'),
            %s, %s, %s
        )
        ON CONFLICT (paciente_id) DO UPDATE SET
            nombre_completo = EXCLUDED.nombre_completo,
            rut = EXCLUDED.rut,
            rut_hash = EXCLUDED.rut_hash,
            fecha_nacimiento = EXCLUDED.fecha_nacimiento,
            sexo_biologico = EXCLUDED.sexo_biologico
    """

    sql_contacto = """
        INSERT INTO contacto_paciente (
            paciente_id, direccion, telefono, email
        )
        VALUES (
            %s::uuid,
            pgp_sym_encrypt(%s::text, %s::text, 'cipher-algo=aes256'),
            pgp_sym_encrypt(%s::text, %s::text, 'cipher-algo=aes256'),
            pgp_sym_encrypt(%s::text, %s::text, 'cipher-algo=aes256')
        )
        ON CONFLICT (paciente_id) DO UPDATE SET
            direccion = EXCLUDED.direccion,
            telefono = EXCLUDED.telefono,
            email = EXCLUDED.email
    """

    sql_consentimiento = """
        INSERT INTO consentimiento (
            consentimiento_id, paciente_id, otorgado,
            tipo_consentimiento, version_texto
        )
        VALUES (%s::uuid, %s::uuid, true, %s, %s)
        ON CONFLICT (consentimiento_id) DO NOTHING
    """

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for paciente in PACIENTES_DEMO:
                cuerpo = paciente["rut_cuerpo"]
                rut = normalizar_rut(f"{cuerpo}-{calcular_dv(cuerpo)}")
                rut_formateado = formatear_rut(rut)
                rut_hash = calcular_rut_hash(rut_formateado)

                cur.execute(
                    sql_paciente,
                    (
                        paciente["id"],
                        paciente["nombre"],
                        rut_formateado,
                        encryption_key,
                        rut_hash,
                        paciente["nacimiento"],
                        paciente["sexo"],
                    ),
                )

                cur.execute(
                    sql_contacto,
                    (
                        paciente["id"],
                        paciente["direccion"],
                        encryption_key,
                        paciente["telefono"],
                        encryption_key,
                        paciente["email"],
                        encryption_key,
                    ),
                )

                cur.execute(
                    sql_consentimiento,
                    (
                        paciente["consentimiento_id"],
                        paciente["id"],
                        CONSENT_TIPO,
                        CONSENT_VERSION_ACTUAL,
                    ),
                )

    print("Seed demo completado: 2 pacientes sintéticos y sus consentimientos.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tareas administrativas puntuales de MediTriage."
    )
    parser.add_argument(
        "comando",
        choices=("seed-roles", "seed-demo"),
        help="Tarea administrativa que se ejecutará.",
    )
    args = parser.parse_args()

    try:
        if args.comando == "seed-roles":
            seed_roles()
        elif args.comando == "seed-demo":
            seed_demo()
    except Exception as exc:
        print(f"Error ejecutando {args.comando}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
