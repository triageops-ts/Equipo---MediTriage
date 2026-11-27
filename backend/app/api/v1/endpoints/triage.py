import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import ValidationError

from app import audit
from app.ai import engine
from app.ai.contrato import EntradaIA

from app.core.auth import requiere_rol
from app.core.security import Usuario
from app.db import get_conn
from app.core.realtime import EVENTO_EVALUACION_CONFIRMADA, publicar_evento
from app.core.sanitizer import sanitize_symptoms_text
from app.schemas.decision import (
    JUSTIFICACION_MIN_CARACTERES,
    DecisionInput,
    DecisionResponse,
)
from app.schemas.cola import (
    ESTADOS_ACTIVOS,
    LIMIT_MAXIMO,
    LIMIT_POR_DEFECTO,
    ColaTriageItem,
    ResumenColaTriage,
    EstadoEpisodio,
    PatientSummary,
)
from app.schemas.evaluacion import ClasificacionIAResponse
from app.schemas.triage import FormularioClinicoInput, FormularioClinicoResponse

logger = logging.getLogger("meditriage.triage")

router = APIRouter(prefix="/triage")

ESTADO_INICIAL = "en_espera"

_EXISTE_PACIENTE = "SELECT 1 FROM paciente WHERE paciente_id = %(patient_id)s"
_EXISTE_USUARIO = (
    "SELECT 1 FROM usuario_staff WHERE usuario_id = %(usuario_id)s AND activo"
)


def _verificar_usuario(cur, usuario: Usuario) -> None:
    """El id sale del token; si el usuario fue dado de baja, el token deja de servir."""
    cur.execute(_EXISTE_USUARIO, {"usuario_id": usuario.usuario_id})
    if not cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario de la sesión ya no está activo.",
        )

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

_INSERT_SINTOMA = """
    INSERT INTO sintomas_triage
        (sintoma_id, episodio_id, codigo_sintoma, severidad,
         tiempo_evolucion_horas)
    VALUES
        (%(sintoma_id)s, %(episodio_id)s, %(codigo_sintoma)s,
         %(severidad)s, %(tiempo_evolucion_horas)s)
"""


@router.post(
    "/formulario",
    response_model=FormularioClinicoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Triages"],
    summary="Registra el formulario clínico (signos vitales y síntomas) de un paciente",
)
def crear_formulario(
    data: FormularioClinicoInput,
    usuario: Usuario = Depends(requiere_rol("enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    episodio_id = uuid.uuid4()
    signos_vitales_id = uuid.uuid4()
    signos = data.signos_vitales.model_dump()

    # Episodio, signos vitales y síntomas se guardan juntos.
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(_EXISTE_PACIENTE, {"patient_id": data.patient_id})
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No existe un paciente registrado con id {data.patient_id}.",
                )

            _verificar_usuario(cur, usuario)

            cur.execute(
                _INSERT_EPISODIO,
                {
                    "episodio_id": episodio_id,
                    "patient_id": data.patient_id,
                    "usuario_id": usuario.usuario_id,
                    "motivo": (
                        sanitize_symptoms_text(data.motivo_consulta)
                        if data.motivo_consulta
                        else None
                    ),
                    "estado": ESTADO_INICIAL,
                },
            )
            fecha_ingreso = cur.fetchone()[0]

            cur.execute(
                _INSERT_SIGNOS,
                {
                    "signos_vitales_id": signos_vitales_id,
                    "episodio_id": episodio_id,
                    **signos,
                },
            )

            for sintoma in data.sintomas:
                cur.execute(
                    _INSERT_SINTOMA,
                    {
                        "sintoma_id": uuid.uuid4(),
                        "episodio_id": episodio_id,
                        **sintoma.model_dump(),
                    },
                )

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
_BLOQUEAR_EPISODIO = (
    "SELECT 1 FROM episodio_triage WHERE episodio_id = %(episodio_id)s FOR UPDATE"
)

_ULTIMA_SUGERENCIA_IA = """
    SELECT nivel_esi_sugerido
    FROM clasificacion_ia
    WHERE episodio_id = %(episodio_id)s
    ORDER BY tiempo_respuesta DESC NULLS LAST
    LIMIT 1
"""

_YA_TIENE_DECISION = (
    "SELECT 1 FROM decision_clinica WHERE episodio_id = %(episodio_id)s"
)

_INSERT_DECISION = """
    INSERT INTO decision_clinica
        (decision_id, episodio_id, nivel_esi_final, usuario_id,
         coincide_con_ia, fecha_hora_decision, justificacion)
    VALUES
        (%(decision_id)s, %(episodio_id)s, %(nivel_esi_final)s, %(usuario_id)s,
         %(coincide_con_ia)s, (now() AT TIME ZONE 'UTC'), %(justificacion)s)
    RETURNING fecha_hora_decision
"""


@router.get(
    "/{episodio_id}/decision",
    response_model=DecisionResponse,
    tags=["Triages"],
    summary="Consulta la decisión final registrada para un episodio",
)
def obtener_decision(
    episodio_id: UUID,
    usuario: Usuario = Depends(requiere_rol("enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    with conn.cursor() as cur:
        _verificar_usuario(cur, usuario)

        cur.execute(
            """
            SELECT
                dc.decision_id,
                dc.episodio_id,
                cia.nivel_esi_sugerido,
                dc.nivel_esi_final,
                dc.coincide_con_ia,
                dc.justificacion,
                dc.usuario_id,
                dc.fecha_hora_decision
            FROM decision_clinica dc
            JOIN LATERAL (
                SELECT nivel_esi_sugerido
                FROM clasificacion_ia
                WHERE episodio_id = dc.episodio_id
                ORDER BY tiempo_respuesta DESC NULLS LAST
                LIMIT 1
            ) cia ON TRUE
            WHERE dc.episodio_id = %(episodio_id)s
            """,
            {"episodio_id": episodio_id},
        )
        fila = cur.fetchone()

    if not fila:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El episodio no tiene una decisión registrada.",
        )

    return DecisionResponse(
        decision_id=fila[0],
        episodio_id=fila[1],
        nivel_esi_sugerido=fila[2],
        nivel_esi_final=fila[3],
        coincide_con_ia=fila[4],
        modificado_manualmente=not fila[4],
        justificacion=fila[5],
        usuario_id=fila[6],
        fecha_hora_decision=fila[7],
    )

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
    usuario: Usuario = Depends(requiere_rol("enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    decision_id = uuid.uuid4()

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(_BLOQUEAR_EPISODIO, {"episodio_id": episodio_id})
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No existe un episodio de triage con id {episodio_id}.",
                )

            _verificar_usuario(cur, usuario)

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
                    "usuario_id": usuario.usuario_id,
                    "coincide_con_ia": coincide,
                    "justificacion": data.justificacion,
                },
            )
            fecha_decision = cur.fetchone()[0]

            # Misma transacción: si el log falla, la decisión también se revierte.
            audit.registrar_evento(
                cur,
                episodio_id=episodio_id,
                decision_id=decision_id,
                evento_tipo=(
                    audit.EVENTO_DECISION_CONFIRMADA
                    if coincide
                    else audit.EVENTO_DECISION_MODIFICADA
                ),
                usuario_id_actor=usuario.usuario_id,
                sugerencia_ia=nivel_sugerido,
                decision_final=data.nivel_esi_final,
            )

    # La decisión ya quedó guardada (la transacción terminó): recién ahora se avisa
    # al tablero. Si Redis falla, publicar_evento solo deja un aviso en el log.
    publicar_evento(
        EVENTO_EVALUACION_CONFIRMADA,
        {
            "decision_id": str(decision_id),
            "episodio_id": str(episodio_id),
            "usuario_id": str(usuario.usuario_id),
            "nivel_esi_definitivo": data.nivel_esi_final,
            "es_sobrescritura": not coincide,
            "fecha_hora_decision": fecha_decision.isoformat(),
        },
    )

    return DecisionResponse(
        decision_id=decision_id,
        episodio_id=episodio_id,
        nivel_esi_sugerido=nivel_sugerido,
        nivel_esi_final=data.nivel_esi_final,
        coincide_con_ia=coincide,
        modificado_manualmente=not coincide,
        justificacion=data.justificacion,
        usuario_id=usuario.usuario_id,
        fecha_hora_decision=fecha_decision,
    )

@router.post(
    "/{episodio_id}/decision/fallo",
    status_code=status.HTTP_201_CREATED,
    tags=["Triages"],
    summary="Registra un fallo confirmado al guardar una decisión clínica",
)
def registrar_fallo_decision(
    episodio_id: UUID,
    data: DecisionInput,
    usuario: Usuario = Depends(requiere_rol("enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    with conn.transaction():
        with conn.cursor() as cur:
            _verificar_usuario(cur, usuario)

            cur.execute(
                "SELECT 1 FROM episodio_triage WHERE episodio_id = %(episodio_id)s",
                {"episodio_id": episodio_id},
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No existe el episodio de triage.",
                )

            cur.execute(
                _ULTIMA_SUGERENCIA_IA,
                {"episodio_id": episodio_id},
            )
            sugerencia = cur.fetchone()

            if not sugerencia:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No existe una sugerencia de IA para el episodio.",
                )

            nivel_sugerido = sugerencia[0]
            registro_id = audit.registrar_evento(
                cur,
                episodio_id=episodio_id,
                evento_tipo=audit.EVENTO_DECISION_FALLIDA,
                usuario_id_actor=usuario.usuario_id,
                sugerencia_ia=nivel_sugerido,
                decision_final=data.nivel_esi_final,
            )

    return {
        "registro_id": str(registro_id),
        "evento_tipo": audit.EVENTO_DECISION_FALLIDA,
    }


# --- Sugerencia ESI de la IA (S09-7) ----------------------------------------

_EPISODIO_PARA_IA = """
    SELECT paciente_id, motivo_consulta_texto_libre
    FROM episodio_triage
    WHERE episodio_id = %(episodio_id)s
    FOR UPDATE
"""

_PACIENTE_PARA_IA = (
    "SELECT fecha_nacimiento, sexo_biologico FROM paciente WHERE paciente_id = %(paciente_id)s"
)

_CAMPOS_SIGNOS = (
    "presion_sistolica", "presion_diastolica", "frecuencia_cardiaca",
    "frecuencia_respiratoria", "temperatura", "saturacion_oxigeno",
    "escala_dolor", "nivel_conciencia",
)

_ULTIMOS_SIGNOS = f"""
    SELECT {", ".join(_CAMPOS_SIGNOS)}
    FROM signos_vitales
    WHERE episodio_id = %(episodio_id)s
    ORDER BY fecha_hora_medicion DESC
    LIMIT 1
"""

_SINTOMAS_PARA_IA = """
    SELECT codigo_sintoma, severidad, tiempo_evolucion_horas
    FROM sintomas_triage
    WHERE episodio_id = %(episodio_id)s
"""

_COLUMNAS_CLASIFICACION = """
    clasificacion_id, nivel_esi_sugerido, justificacion_ia, modelo_usado,
    fallback_aplicado, tiempo_solicitud, tiempo_respuesta
"""

_CLASIFICACION_POR_CLAVE = f"""
    SELECT {_COLUMNAS_CLASIFICACION}
    FROM clasificacion_ia
    WHERE episodio_id = %(episodio_id)s AND idempotency_key = %(idempotency_key)s
"""

_INSERT_CLASIFICACION = """
    INSERT INTO clasificacion_ia
        (clasificacion_id, episodio_id, token_correlacion_efimero, nivel_esi_sugerido,
         tiempo_solicitud, tiempo_respuesta, modelo_usado, hash_datos_enviados_ia,
         justificacion_ia, fallback_aplicado, idempotency_key)
    VALUES
        (%(clasificacion_id)s, %(episodio_id)s, %(token)s, %(nivel)s,
         %(tiempo_solicitud)s, %(tiempo_respuesta)s, %(modelo)s, %(hash)s,
         %(justificacion)s, %(fallback)s, %(idempotency_key)s)
"""

_SEXO_A_CONTRATO = {"masculino": "masculino", "femenino": "femenino"}
# La API pública usa los valores en inglés (igual que GET /patients).
_SEXO_A_API = {"masculino": "male", "femenino": "female"}


def _edad_anios(nacimiento: date, hoy: date) -> int:
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def _ahora_utc() -> datetime:
    # Las columnas son DateTime sin zona: se guarda UTC naive, igual que el resto de las tablas.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _latencia_ms(solicitud: datetime, respuesta: datetime) -> int:
    return max(0, int((respuesta - solicitud).total_seconds() * 1000))


def _sin_datos(detalle: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detalle)


def _armar_entrada(cur, episodio_id: UUID, paciente_id: UUID, motivo: Optional[str]) -> EntradaIA:
    """Arma el payload para la IA solo con los campos del contrato (S09-4).

    Nunca se leen nombre, RUT, contactos ni el id del paciente: de `paciente` solo salen
    la fecha de nacimiento (para calcular la edad, que es lo único que viaja) y el sexo.
    """
    cur.execute(_PACIENTE_PARA_IA, {"paciente_id": paciente_id})
    paciente = cur.fetchone()
    if not paciente or paciente[0] is None:
        raise _sin_datos(
            "El paciente no tiene fecha de nacimiento registrada; no se puede calcular la edad para la IA."
        )
    nacimiento, sexo = paciente

    cur.execute(_ULTIMOS_SIGNOS, {"episodio_id": episodio_id})
    fila = cur.fetchone()
    if not fila:
        raise _sin_datos("El episodio no tiene signos vitales registrados.")
    signos = dict(zip(_CAMPOS_SIGNOS, fila))
    # La base guarda la saturación como float; el contrato pide un entero.
    signos["saturacion_oxigeno"] = int(round(signos["saturacion_oxigeno"]))

    cur.execute(_SINTOMAS_PARA_IA, {"episodio_id": episodio_id})
    sintomas = [
        {"codigo_sintoma": c, "severidad": sev, "tiempo_evolucion_horas": h}
        for c, sev, h in cur.fetchall()
    ]

    try:
        return EntradaIA(
            edad_anios=_edad_anios(nacimiento, _ahora_utc().date()),
            sexo_biologico=_SEXO_A_CONTRATO.get(sexo),
            signos_vitales=signos,
            sintomas=sintomas,
            motivo_consulta=motivo,
        )
    except ValidationError:
        # Sin detalle: el mensaje de Pydantic podría repetir valores del paciente.
        raise _sin_datos("Los datos clínicos del episodio no cumplen el contrato de la IA.") from None


def _respuesta_clasificacion(episodio_id: UUID, fila) -> ClasificacionIAResponse:
    (clasificacion_id, nivel, justificacion, modelo, fallback, t_solicitud, t_respuesta) = fila
    return ClasificacionIAResponse(
        clasificacion_id=clasificacion_id,
        episodio_id=episodio_id,
        nivel_esi_sugerido=nivel,
        justificacion_ia=justificacion,
        modelo_usado=modelo,
        fallback_aplicado=fallback,
        latencia_ms=_latencia_ms(t_solicitud, t_respuesta or t_solicitud),
        fecha_hora_solicitud=t_solicitud,
    )


@router.post(
    "/{episodio_id}/evaluate",
    response_model=ClasificacionIAResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Triages"],
    summary="Pide a la IA un nivel ESI sugerido para un episodio ya registrado",
)
def evaluar_episodio(
    episodio_id: UUID,
    usuario: Usuario = Depends(requiere_rol("enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
    idempotency_key: Optional[UUID] = Header(default=None, alias="Idempotency-Key"),
):
    # Todo ocurre en una transacción con el episodio bloqueado: dos evaluaciones
    # simultáneas del mismo episodio (o el mismo Idempotency-Key repetido) no se pisan.
    # La espera máxima por la IA es de 1500 ms (ver app/ai/engine.py).
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(_EPISODIO_PARA_IA, {"episodio_id": episodio_id})
            episodio = cur.fetchone()
            if not episodio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No existe un episodio de triage con id {episodio_id}.",
                )
            paciente_id, motivo = episodio

            _verificar_usuario(cur, usuario)

            if idempotency_key is not None:
                cur.execute(
                    _CLASIFICACION_POR_CLAVE,
                    {"episodio_id": episodio_id, "idempotency_key": idempotency_key},
                )
                previa = cur.fetchone()
                if previa:
                    return _respuesta_clasificacion(episodio_id, previa)

            entrada = _armar_entrada(cur, episodio_id, paciente_id, motivo)

            # engine.clasificar nunca lanza por culpa de la IA: si falla o pasa de
            # 1500 ms devuelve el árbol de reglas con fallback_aplicado=True.
            t_solicitud = _ahora_utc()
            resultado = engine.clasificar(entrada)
            t_respuesta = _ahora_utc()

            clasificacion_id = uuid.uuid4()
            cur.execute(
                _INSERT_CLASIFICACION,
                {
                    "clasificacion_id": clasificacion_id,
                    "episodio_id": episodio_id,
                    "token": uuid.uuid4(),  # no se puede vincular al paciente fuera de la base
                    "nivel": resultado.nivel_esi_sugerido,
                    "tiempo_solicitud": t_solicitud,
                    "tiempo_respuesta": t_respuesta,
                    "modelo": resultado.modelo_usado,
                    "hash": engine.hash_entrada(entrada),
                    "justificacion": resultado.justificacion,
                    "fallback": resultado.fallback_aplicado,
                    "idempotency_key": idempotency_key,
                },
            )

            # Misma transacción: guarda el prompt sanitizado que viajó a la IA.
            audit.registrar_evento(
                cur,
                episodio_id=episodio_id,
                evento_tipo=(
                    audit.EVENTO_RESPALDO_APLICADO
                    if resultado.fallback_aplicado
                    else audit.EVENTO_IA_SUGERIDA
                ),
                usuario_id_actor=usuario.usuario_id,
                sugerencia_ia=resultado.nivel_esi_sugerido,
                prompt_enviado=engine.registro_inferencia(entrada, resultado),
            )

    latencia = _latencia_ms(t_solicitud, t_respuesta)
    # Solo ids y métricas: ni signos vitales, ni síntomas, ni justificación.
    logger.info(
        "ia_evaluacion_guardada",
        extra={
            "clasificacion_id": str(clasificacion_id),
            "nivel_esi_sugerido": resultado.nivel_esi_sugerido,
            "fallback_aplicado": resultado.fallback_aplicado,
            "latencia_ms": latencia,
        },
    )

    return ClasificacionIAResponse(
        clasificacion_id=clasificacion_id,
        episodio_id=episodio_id,
        nivel_esi_sugerido=resultado.nivel_esi_sugerido,
        justificacion_ia=resultado.justificacion,
        modelo_usado=resultado.modelo_usado,
        fallback_aplicado=resultado.fallback_aplicado,
        latencia_ms=latencia,
        fecha_hora_solicitud=t_solicitud,
    )


# --- Cola priorizada (S10-3) -------------------------------------------------

# Nivel vigente: el final si la enfermera ya decidió; si no, el último sugerido por la IA.
# Orden: ESI ascendente (1 arriba); a igual nivel, el que lleva más tiempo esperando.
# Los episodios aún sin nivel van al final. episodio_id desempata para que la
# paginación sea estable entre páginas.
# Con con_decision=true solo entran los episodios que la enfermera ya confirmó o
# sobrescribió (tienen decision_clinica): así el tablero médico no muestra casos en
# evaluación, ni en la carga inicial ni en la recarga periódica.
# Del paciente solo se leen fecha de nacimiento y sexo: nunca nombre ni RUT.
_COLA_TRIAGE = """
    SELECT
        e.episodio_id,
        e.paciente_id,
        p.fecha_nacimiento,
        p.sexo_biologico,
        e.estado,
        cia.nivel_esi_sugerido,
        dc.nivel_esi_final,
        e.fecha_hora_ingreso,
        GREATEST(
            0,
            floor(extract(epoch FROM ((now() AT TIME ZONE 'UTC') - e.fecha_hora_ingreso)) / 60)
        )::int AS minutos_espera
    FROM episodio_triage e
    JOIN paciente p ON p.paciente_id = e.paciente_id
    LEFT JOIN LATERAL (
        SELECT nivel_esi_sugerido
        FROM clasificacion_ia
        WHERE episodio_id = e.episodio_id
        ORDER BY tiempo_respuesta DESC NULLS LAST
        LIMIT 1
    ) cia ON TRUE
    LEFT JOIN decision_clinica dc ON dc.episodio_id = e.episodio_id
    WHERE e.estado = ANY(%(estados)s)
      AND (NOT %(con_decision)s::boolean OR dc.episodio_id IS NOT NULL)
      AND (
          %(nivel_esi)s::int IS NULL
          OR COALESCE(dc.nivel_esi_final, cia.nivel_esi_sugerido) = %(nivel_esi)s::int
      )
    ORDER BY
        COALESCE(dc.nivel_esi_final, cia.nivel_esi_sugerido) ASC NULLS LAST,
        e.fecha_hora_ingreso ASC,
        e.episodio_id ASC
    OFFSET %(skip)s
    LIMIT %(limit)s
"""


@router.get(
    "/cola",
    response_model=list[ColaTriageItem],
    tags=["Triages"],
    summary="Cola de triage priorizada por nivel ESI y tiempo de espera",
    description=(
        "Lista inicial del tablero médico y la sala de espera, antes de las "
        "actualizaciones en vivo. ESI 1 arriba; a igual nivel, el que lleva más "
        "tiempo esperando. Sin filtro de estado devuelve los episodios abiertos "
        "(en_espera y en_atencion). No incluye RUT ni nombre del paciente."
    ),
)
def listar_cola(
    estado: Optional[EstadoEpisodio] = Query(
        default=None, description="Filtra por estado del episodio."
    ),
    nivel_esi: Optional[int] = Query(
        default=None,
        ge=1,
        le=5,
        description="Filtra por nivel ESI vigente (el final si ya hay decisión, si no el sugerido).",
    ),
    con_decision: bool = Query(
        default=False,
        description=(
            "Solo episodios con decisión clínica (ESI confirmado o sobrescrito por enfermería). "
            "Lo usa el tablero médico."
        ),
    ),
    skip: int = Query(default=0, ge=0, description="Registros a saltar (paginación)."),
    limit: int = Query(
        default=LIMIT_POR_DEFECTO,
        ge=1,
        le=LIMIT_MAXIMO,
        description="Cantidad máxima de registros a devolver.",
    ),
    usuario: Usuario = Depends(requiere_rol("medico", "enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    with conn.cursor() as cur:
        _verificar_usuario(cur, usuario)
        cur.execute(
            _COLA_TRIAGE,
            {
                "estados": [estado] if estado else list(ESTADOS_ACTIVOS),
                "nivel_esi": nivel_esi,
                "con_decision": con_decision,
                "skip": skip,
                "limit": limit,
            },
        )
        filas = cur.fetchall()

    hoy = _ahora_utc().date()
    return [
        ColaTriageItem(
            episodio_id=episodio_id,
            patient=PatientSummary(
                patient_id=paciente_id,
                age=_edad_anios(nacimiento, hoy) if nacimiento else None,
                biological_sex=_SEXO_A_API.get(sexo),
            ),
            estado=estado_ep,
            nivel_esi_sugerido=sugerido,
            nivel_esi_final=final,
            fecha_hora_ingreso=ingreso,
            minutos_espera=minutos,
        )
        for (
            episodio_id, paciente_id, nacimiento, sexo, estado_ep,
            sugerido, final, ingreso, minutos,
        ) in filas
    ]


_RESUMEN_COLA_TRIAGE = """
    SELECT
        COALESCE(dc.nivel_esi_final, cia.nivel_esi_sugerido) AS nivel_esi,
        COUNT(*)::int AS total
    FROM episodio_triage e
    LEFT JOIN LATERAL (
        SELECT nivel_esi_sugerido
        FROM clasificacion_ia
        WHERE episodio_id = e.episodio_id
        ORDER BY tiempo_respuesta DESC NULLS LAST
        LIMIT 1
    ) cia ON TRUE
    LEFT JOIN decision_clinica dc ON dc.episodio_id = e.episodio_id
    WHERE e.estado = ANY(%(estados)s)
      AND (NOT %(con_decision)s::boolean OR dc.episodio_id IS NOT NULL)
    GROUP BY COALESCE(dc.nivel_esi_final, cia.nivel_esi_sugerido)
"""


@router.get(
    "/cola/resumen",
    response_model=ResumenColaTriage,
    tags=["Triages"],
    summary="Resumen global de episodios activos por nivel ESI",
)
def resumen_cola(
    con_decision: bool = Query(
        default=False,
        description="Cuenta solo episodios con decisión clínica, igual que la cola.",
    ),
    usuario: Usuario = Depends(requiere_rol("medico", "enfermero")),
    conn: psycopg.Connection = Depends(get_conn),
):
    with conn.cursor() as cur:
        _verificar_usuario(cur, usuario)
        cur.execute(
            _RESUMEN_COLA_TRIAGE,
            {"estados": list(ESTADOS_ACTIVOS), "con_decision": con_decision},
        )
        filas = cur.fetchall()

    por_nivel = {nivel: 0 for nivel in range(1, 6)}
    sin_nivel = 0

    for nivel, total in filas:
        if nivel is None:
            sin_nivel = total
        elif nivel in por_nivel:
            por_nivel[nivel] = total

    return ResumenColaTriage(
        por_nivel=por_nivel,
        sin_nivel=sin_nivel,
    )
