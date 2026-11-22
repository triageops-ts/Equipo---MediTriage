"""Respuestas de la consulta de auditoría (S10-6, US-05). Contrato: api/openapi.yaml."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    registro_id: UUID
    episodio_id: UUID
    decision_id: Optional[UUID] = None
    evento_tipo: str
    usuario_id_actor: Optional[UUID] = None
    sugerencia_ia: Optional[int] = None
    prompt_enviado: Optional[str] = None
    decision_final: Optional[int] = None
    hay_discrepancia: bool
    hash_anterior: str
    hash_actual: str
    fecha_hora_evento: datetime


class RegistroAlterado(BaseModel):
    registro_id: UUID
    motivo: str


class VerificacionCadena(BaseModel):
    valida: bool
    registros_verificados: int
    # El más antiguo de la cadena; null si la cadena es íntegra.
    primer_registro_alterado: Optional[RegistroAlterado] = None
