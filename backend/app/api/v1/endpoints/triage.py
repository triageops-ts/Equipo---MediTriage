import uuid
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_conn
from app.schemas.decision import (
    JUSTIFICACION_MIN_CARACTERES,
    DecisionInput,
    DecisionResponse,
)
from app.schemas.triage import FormularioClinicoInput, FormularioClinicoResponse

router = APIRouter(prefix="/triage")

ESTADO_INICIAL = "en_espera"

_EXISTE_PACIENTE = "SELECT 1 FROM paciente WHERE paciente_id = %(patient_id)s"
_EXISTE_USUARIO = "SELECT 1 FROM usuario_staff WHERE usuario_id = %(usuario_id)s"

# La fecha la pone la base de datos (UTC), no el cliente.
_INSERT_EPISODIO = """
    INSERT INTO episodio_triage
        (episodio_id, paciente_id, usuario_id, fecha_hora_ingreso,
         motivo_consulta_texto_libre, estado)
    VALUES
        (%(episodio_id)s, %(patient_id)s, %(usuario_id)s, (now() AT TIME ZONE 'UTC'),
         %(motivo)s, %(estado)s)
    RETURNING fecha_hora_ingreso
"""

_INSERT_SIGNOS = """
    INSERT INTO signos_vitales
        (signos_vitales_id, episodio_id, presion_sistolica, presion_diastolica,
         frecuencia_cardiaca, frecuencia_respiratoria, temperatura, saturacion_oxigeno,
         escala_dolor, nivel_conciencia, fecha_hora_medicion)
    VALUES
        (%(signos_vitales_id)s, %(episodio_id)s, %(presion_sistolica)s, %(presion_diastolica)s,
         %(frecuencia_cardiaca)s, %(frecuencia_respiratoria)s, %(temperatura)s,
         %(saturacion_oxigeno)s, %(escala_dolor)s, %(nivel_conciencia)s,
         (now() AT TIME ZONE 'UTC'))
"""


@router.post(
    "/formulario",
    response_model=FormularioClinicoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Triages"],
    summary="Registra el formulario clínico (signos vitales) de un paciente",
)
def crear_formulario(
    data: FormularioClinicoInput, conn: psycopg.Connection = Depends(get_conn)
):
    episodio_id = uuid.uuid4()
    signos_vitales_id = uuid.uuid4()
    signos = data.signos_vitales.model_dump()

    try:
        # Episodio y signos vitales se guardan juntos o no se guarda nada.
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(_EXISTE_PACIENTE, {"patient_id": data.patient_id})
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No existe un paciente registrado con id {data.patient_id}.",
                    )

                if data.usuario_id is not None:
                    cur.execute(_EXISTE_USUARIO, {"usuario_id": data.usuario_id})
                    if not cur.fetchone():
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No existe un usuario con id {data.usuario_id}.",
                        )

                cur.execute(
                    _INSERT_EPISODIO,
                    {
                        "episodio_id": episodio_id,
                        "patient_id": data.patient_id,
                        "usuario_id": data.usuario_id,
                        "motivo": data.motivo_consulta,
                        "estado": ESTADO_INICIAL,
                    },
                )
                fecha_ingreso = cur.fetchone()[0]

                cur.execute(
                    _INSERT_SIGNOS,
                    {"signos_vitales_id": signos_vitales_id, "episodio_id": episodio_id, **signos},
                )
    except psycopg.errors.NotNullViolation as e:
        if e.diag.column_name == "usuario_id":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Falta usuario_id: el episodio debe indicar quién lo registra.",
            ) from None
        raise

    return FormularioClinicoResponse(
        episodio_id=episodio_id,
        signos_vitales_id=signos_vitales_id,
        patient_id=data.patient_id,
        estado=ESTADO_INICIAL,
        fecha_hora_ingreso=fecha_ingreso,
        signos_vitales=data.signos_vitales,
    )

# --- Decisión final de la enfermera -----------------------------------------

# Bloquea el episodio para que dos decisiones simultáneas no se pisen.
_BLOQUEAR_EPISODIO = "SELECT 1 FROM episodio_triage WHERE episodio_id = %(episodio_id)s FOR UPDATE"

_ULTIMA_SUGERENCIA_IA = """
    SELECT nivel_esi_sugerido
    FROM clasificacion_ia
    WHERE episodio_id = %(episodio_id)s
    ORDER BY tiempo_respuesta DESC NULLS LAST
    LIMIT 1
"""

_YA_TIENE_DECISION = "SELECT 1 FROM decision_clinica WHERE episodio_id = %(episodio_id)s"

_INSERT_DECISION = """
    INSERT INTO decision_clinica
        (decision_id, episodio_id, nivel_esi_final, usuario_id,
         coincide_con_ia, fecha_hora_decision, justificacion)
    VALUES
        (%(decision_id)s, %(episodio_id)s, %(nivel_esi_final)s, %(usuario_id)s,
         %(coincide_con_ia)s, (now() AT TIME ZONE 'UTC'), %(justificacion)s)
    RETURNING fecha_hora_decision
"""


@router.post(
    "/{episodio_id}/decision",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Triages"],
    summary="Guarda la decisión final: confirma o modifica el nivel ESI sugerido por la IA",
)
def registrar_decision(
    episodio_id: UUID,
    data: DecisionInput,
    conn: psycopg.Connection = Depends(get_conn),
):
    decision_id = uuid.uuid4()

    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(_BLOQUEAR_EPISODIO, {"episodio_id": episodio_id})
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No existe un episodio de triage con id {episodio_id}.",
                    )

                if data.usuario_id is not None:
                    cur.execute(_EXISTE_USUARIO, {"usuario_id": data.usuario_id})
                    if not cur.fetchone():
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No existe un usuario con id {data.usuario_id}.",
                        )

                cur.execute(_ULTIMA_SUGERENCIA_IA, {"episodio_id": episodio_id})
                sugerencia = cur.fetchone()
                if not sugerencia:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="El episodio aún no tiene una sugerencia de la IA que confirmar o modificar.",
                    )
                nivel_sugerido = sugerencia[0]

                cur.execute(_YA_TIENE_DECISION, {"episodio_id": episodio_id})
                if cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="El episodio ya tiene una decisión registrada; no se puede reemplazar.",
                    )

                coincide = data.nivel_esi_final == nivel_sugerido
                if not coincide and (
                    data.justificacion is None
                    or len(data.justificacion) < JUSTIFICACION_MIN_CARACTERES
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"Para cambiar el nivel ESI sugerido por la IA ({nivel_sugerido}) "
                            f"debe explicar el motivo (mínimo {JUSTIFICACION_MIN_CARACTERES} caracteres)."
                        ),
                    )

                cur.execute(
                    _INSERT_DECISION,
                    {
                        "decision_id": decision_id,
                        "episodio_id": episodio_id,
                        "nivel_esi_final": data.nivel_esi_final,
                        "usuario_id": data.usuario_id,
                        "coincide_con_ia": coincide,
                        "justificacion": data.justificacion,
                    },
                )
                fecha_decision = cur.fetchone()[0]
    except psycopg.errors.NotNullViolation as e:
        if e.diag.column_name == "usuario_id":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Falta usuario_id: la decisión debe indicar quién la toma.",
            ) from None
        raise

    return DecisionResponse(
        decision_id=decision_id,
        episodio_id=episodio_id,
        nivel_esi_sugerido=nivel_sugerido,
        nivel_esi_final=data.nivel_esi_final,
        coincide_con_ia=coincide,
        modificado_manualmente=not coincide,
        justificacion=data.justificacion,
        usuario_id=data.usuario_id,
        fecha_hora_decision=fecha_decision,
    )