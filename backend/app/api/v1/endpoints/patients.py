import logging
import uuid

import psycopg
from psycopg import sql
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import requiere_rol
from app.core.consent import CONSENT_TIPO
from app.core.rut import RutInvalido, formatear_rut, normalizar_rut
from app.core.rut_hash import calcular_rut_hash
from app.db import encryption_key, get_conn
from app.schemas.patient import Patient, PatientFound, PatientInput, PatientUpdate

router = APIRouter()
logger = logging.getLogger("meditriage.patients")

_SEXO_A_DB = {"male": "masculino", "female": "femenino"}

_LOCK_RUT = "SELECT pg_advisory_xact_lock(hashtextextended(%(rut)s::text, 0))"

_EXISTE_RUT = "SELECT 1 FROM paciente WHERE rut_hash = %(rut_hash)s LIMIT 1"

_INSERT_PACIENTE = """
    INSERT INTO paciente (paciente_id, nombre_completo, rut, rut_hash, fecha_nacimiento, sexo_biologico)
    VALUES (
        %(paciente_id)s,
        %(nombre)s,
        pgp_sym_encrypt(%(rut)s::text, %(key)s::text, 'cipher-algo=aes256'),
        %(rut_hash)s,
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
def create_patient(
    data: PatientInput,
    _usuario=Depends(requiere_rol("enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    key = encryption_key()
    rut_formateado = formatear_rut(data.rut)
    rut_hash = calcular_rut_hash(rut_formateado)
    paciente_id = uuid.uuid4()
    consentimiento_id = uuid.uuid4()

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(_LOCK_RUT, {"rut": rut_formateado})
            cur.execute(_EXISTE_RUT, {"rut_hash": rut_hash})
            if cur.fetchone():
                logger.warning("patient_create_conflict")  # sin RUT
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
                    "rut_hash": rut_hash,
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

    # Solo ids opacos y banderas: nada de nombre, RUT ni datos de contacto.
    logger.info(
        "patient_created",
        extra={
            "patient_id": str(paciente_id),
            "consent_version": data.consent_version,
            "has_contact_data": bool(data.address or data.phone or data.email),
        },
    )
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

_SEXO_A_API = {"masculino": "male", "femenino": "female"}

_BUSCAR_POR_RUT = """
    SELECT paciente_id, nombre_completo, fecha_nacimiento, sexo_biologico
    FROM paciente
    WHERE rut_hash = %(rut_hash)s
    LIMIT 1
"""


@router.get(
    "/patients",
    response_model=list[PatientFound],
    tags=["Pacientes"],
    summary="Busca un paciente por RUT",
)
def list_patients(
    rut: str = Query(..., description="RUT del paciente, con o sin puntos y guion."),
    _usuario=Depends(requiere_rol("enfermero", "medico")),
    conn: psycopg.Connection = Depends(get_conn),
):
    try:
        rut_formateado = formatear_rut(normalizar_rut(rut))
    except RutInvalido as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from None

    with conn.cursor() as cur:
        cur.execute(_BUSCAR_POR_RUT, {"rut_hash": calcular_rut_hash(rut_formateado)})
        filas = cur.fetchall()

    return [
        PatientFound(
            patient_id=paciente_id,
            rut=rut_formateado,
            name=nombre,
            birth_date=fecha_nacimiento,
            biological_sex=_SEXO_A_API.get(sexo),
        )
        for paciente_id, nombre, fecha_nacimiento, sexo in filas
    ]


# Campo de la API -> columna de paciente. Solo estos se pueden editar (el RUT no).
_COLUMNA_EDITABLE = {
    "name": "nombre_completo",
    "birth_date": "fecha_nacimiento",
    "biological_sex": "sexo_biologico",
}


@router.patch(
    "/patients/{patient_id}",
    response_model=PatientFound,
    tags=["Pacientes"],
    summary="Corrige los datos de un paciente",
)
def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    usuario=Depends(requiere_rol("enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    campos = sorted(data.model_fields_set)
    valores = {
        "name": data.name,
        "birth_date": data.birth_date,
        "biological_sex": _SEXO_A_DB.get(data.biological_sex) if data.biological_sex else None,
    }
    parametros = {_COLUMNA_EDITABLE[c]: valores[c] for c in campos}
    parametros.update({"paciente_id": patient_id, "key": encryption_key()})

    # Los nombres de columna salen de _COLUMNA_EDITABLE (fijos), nunca del cliente.
    consulta = sql.SQL(
        "UPDATE paciente SET {cambios} WHERE paciente_id = %(paciente_id)s "
        "RETURNING paciente_id, pgp_sym_decrypt(rut, %(key)s::text), nombre_completo, "
        "fecha_nacimiento, sexo_biologico"
    ).format(
        cambios=sql.SQL(", ").join(
            sql.SQL("{} = {}").format(
                sql.Identifier(_COLUMNA_EDITABLE[c]), sql.Placeholder(_COLUMNA_EDITABLE[c])
            )
            for c in campos
        )
    )

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(consulta, parametros)
            fila = cur.fetchone()

    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe un paciente con ese identificador.",
        )

    # Quién cambió qué campos, sin los valores (nada de nombre ni fecha en el log).
    logger.info(
        "patient_updated",
        extra={
            "patient_id": str(patient_id),
            "actor_id": str(usuario.usuario_id),
            "fields": campos,
        },
    )
    paciente_id, rut, nombre, fecha_nacimiento, sexo = fila
    return PatientFound(
        patient_id=paciente_id,
        rut=rut,
        name=nombre,
        birth_date=fecha_nacimiento,
        biological_sex=_SEXO_A_API.get(sexo),
    )
