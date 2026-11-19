"""Escritura automática de la auditoría clínico-algorítmica (S10-4, US-05).

registrar_evento(cur, ...) se llama con el cursor de la MISMA transacción que guarda el
hecho clínico (clasificación de la IA, decisión de la enfermera). Si el INSERT del log
falla, se lanza un error 500 y la transacción completa se revierte: no puede existir un
hecho clínico sin su registro de auditoría.

hash_anterior, hash_actual y fecha_hora_evento los calcula un trigger en la base
(migración 0011); aquí no se envían. prompt_enviado se vuelve a sanitizar por seguridad.
"""
import logging
import uuid
from typing import Optional
from uuid import UUID

import psycopg
from fastapi import HTTPException, status

from app.core.sanitizer import sanitize_symptoms_text

logger = logging.getLogger("meditriage.audit")

# Nombres del catálogo de eventos (docs/data/event-catalog.md).
EVENTO_IA_SUGERIDA = "ia.clasificacion.sugerida"
EVENTO_RESPALDO_APLICADO = "triage.clasificacion.respaldo_aplicada"
EVENTO_DECISION_CONFIRMADA = "triage.evaluacion.confirmada"
EVENTO_DECISION_MODIFICADA = "triage.override.ejecutado"
EVENTO_DECISION_FALLIDA = "triage.decision.guardar_fallido"

_INSERT = """
    INSERT INTO registro_auditoria
        (registro_id, episodio_id, decision_id, evento_tipo, usuario_id_actor,
         sugerencia_ia, prompt_enviado, decision_final, hay_discrepancia)
    VALUES
        (%(registro_id)s, %(episodio_id)s, %(decision_id)s, %(evento_tipo)s,
         %(usuario_id_actor)s, %(sugerencia_ia)s, %(prompt_enviado)s,
         %(decision_final)s, %(hay_discrepancia)s)
"""


def registrar_evento(
    cur,
    *,
    episodio_id: UUID,
    evento_tipo: str,
    usuario_id_actor: UUID,
    sugerencia_ia: Optional[int] = None,
    decision_final: Optional[int] = None,
    prompt_enviado: Optional[str] = None,
    decision_id: Optional[UUID] = None,
    hay_discrepancia: Optional[bool] = None,
) -> UUID:
    """Inserta un registro de auditoría en la transacción del cursor. Nunca hace commit."""
    if hay_discrepancia is None:
        hay_discrepancia = (
            sugerencia_ia is not None
            and decision_final is not None
            and sugerencia_ia != decision_final
        )
    registro_id = uuid.uuid4()
    try:
        cur.execute(
            _INSERT,
            {
                "registro_id": registro_id,
                "episodio_id": episodio_id,
                "decision_id": decision_id,
                "evento_tipo": evento_tipo,
                "usuario_id_actor": usuario_id_actor,
                "sugerencia_ia": sugerencia_ia,
                "prompt_enviado": (
                    sanitize_symptoms_text(prompt_enviado) if prompt_enviado else None
                ),
                "decision_final": decision_final,
                "hay_discrepancia": hay_discrepancia,
            },
        )
    except psycopg.Error as exc:
        # Solo el tipo de error: ni el prompt ni datos del paciente van al log técnico.
        logger.error(
            "auditoria_registro_fallido",
            extra={"evento_tipo": evento_tipo, "error": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la auditoría; la operación fue revertida.",
        ) from None
    return registro_id


def verificar_cadena(cur) -> list[tuple[UUID, str]]:
    """Registros con la cadena rota (lista vacía = íntegra). Ejecutar como auditor."""
    cur.execute("SELECT registro_id, motivo FROM verificar_cadena_auditoria()")
    return cur.fetchall()
