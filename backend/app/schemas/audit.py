"""Esquemas del aviso de fallo de guardado que envía el navegador."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Tipo de fallo de conexión (nunca texto libre: así no puede colarse PII).
TipoErrorConexion = Literal["red", "timeout_servidor", "servidor_no_disponible"]


class EventoFalloGuardadoInput(BaseModel):
    """Datos mínimos para auditar que el guardado de una decisión falló.

    A propósito NO incluye el nivel ESI, la justificación ni datos del paciente:
    la bitácora registra QUE falló y cuántas veces, no el contenido clínico.
    """

    model_config = ConfigDict(extra="forbid")

    episodio_id: UUID
    usuario_id: UUID | None = None
    tipo_error: TipoErrorConexion
    intentos: int = Field(strict=True, ge=1, le=50)
    # True si al final el guardado se logró; False si quedó pendiente.
    recuperado: bool = Field(strict=True)
    # Hora del navegador del primer fallo. Es informativa: la hora oficial
    # del registro la pone la base de datos.
    primer_fallo_cliente: datetime


class EventoAuditoriaResponse(BaseModel):
    registro_id: UUID
    evento_tipo: str
    hash_actual: str
    fecha_hora_evento: datetime