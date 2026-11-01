import uuid

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.consent import CONSENT_TIPO
from app.core.rut import formatear_rut
from app.db import encryption_key, get_conn
from app.schemas.patient import Patient, PatientInput

router = APIRouter()

_SEXO_A_DB = {"male": "masculino", "female": "femenino"}

_LOCK_RUT = "SELECT pg_advisory_xact_lock(hashtextextended(%(rut)s::text, 0))"

_EXISTE_RUT = """
    SELECT 1 FROM paciente
    WHERE pgp_sym_decrypt(rut, %(key)s::text) = %(rut)s::text
    LIMIT 1
"""

_INSERT_PACIENTE = """
    INSERT INTO paciente (paciente_id, nombre_completo, rut, fecha_nacimiento, sexo_biologico)
    VALUES (
        %(paciente_id)s,
        %(nombre)s,
        pgp_sym_encrypt(%(rut)s::text, %(key)s::text, 'cipher-algo=aes256'),
        %(fecha_nacimiento)s,
        %(sexo)s
    )
"""

_INSERT_CONTACTO = """
    INSERT INTO contacto_paciente (paciente_id, direccion, telefono, email)
    VALUES (
        %(paciente_id)s,
        CASE WHEN %(direccion)s::text IS NULL THEN NULL
             ELSE pgp_sym_encrypt(%(direccion)s::text, %(key)s::text, 'cipher-algo=aes256') END,
        CASE WHEN %(telefono)s::text IS NULL THEN NULL
             ELSE pgp_sym_encrypt(%(telefono)s::text, %(key)s::text, 'cipher-algo=aes256') END,
        CASE WHEN %(email)s::text IS NULL THEN NULL
             ELSE pgp_sym_encrypt(%(email)s::text, %(key)s::text, 'cipher-algo=aes256') END
    )
"""

_INSERT_CONSENTIMIENTO = """
    INSERT INTO consentimiento
        (consentimiento_id, paciente_id, otorgado, fecha_hora, tipo_consentimiento, version_texto)
    VALUES
        (%(consentimiento_id)s, %(paciente_id)s, TRUE, (now() AT TIME ZONE 'UTC'),
         %(tipo)s, %(version)s)
    RETURNING fecha_hora
"""


@router.post(
    "/patients",
    response_model=Patient,
    status_code=status.HTTP_201_CREATED,
    tags=["Pacientes"],
    summary="Registra un nuevo paciente",
)
def create_patient(data: PatientInput, conn: psycopg.Connection = Depends(get_conn)):
    key = encryption_key()
    rut_formateado = formatear_rut(data.rut)
    paciente_id = uuid.uuid4()
    consentimiento_id = uuid.uuid4()

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(_LOCK_RUT, {"rut": rut_formateado})
            cur.execute(_EXISTE_RUT, {"rut": rut_formateado, "key": key})
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un paciente registrado con el RUT {rut_formateado}.",
                )

            cur.execute(
                _INSERT_PACIENTE,
                {
                    "paciente_id": paciente_id,
                    "nombre": data.name,
                    "rut": rut_formateado,
                    "key": key,
                    "fecha_nacimiento": data.birth_date,
                    "sexo": _SEXO_A_DB.get(data.biological_sex),
                },
            )

            if data.address or data.phone or data.email:
                cur.execute(
                    _INSERT_CONTACTO,
                    {
                        "paciente_id": paciente_id,
                        "direccion": data.address,
                        "telefono": data.phone,
                        "email": data.email,
                        "key": key,
                    },
                )

            cur.execute(
                _INSERT_CONSENTIMIENTO,
                {
                    "consentimiento_id": consentimiento_id,
                    "paciente_id": paciente_id,
                    "tipo": CONSENT_TIPO,
                    "version": data.consent_version,
                },
            )
            fecha_aceptacion = cur.fetchone()[0]

    return Patient(
        patient_id=paciente_id,
        rut=rut_formateado,
        name=data.name,
        birth_date=data.birth_date,
        biological_sex=data.biological_sex,
        has_consent=True,
        consent_id=consentimiento_id,
        consent_version=data.consent_version,
        consent_accepted_at=fecha_aceptacion,
    )