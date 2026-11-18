"""Respuesta de POST /triage/{episodio_id}/evaluate (schema ClasificacionIA del OpenAPI).

No incluye token_correlacion_efimero ni hash_datos_enviados_ia: son de trazabilidad
interna y no tienen por qué salir de la base.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClasificacionIAResponse(BaseModel):
    clasificacion_id: UUID
    episodio_id: UUID
    nivel_esi_sugerido: int
    justificacion_ia: str
    modelo_usado: str
    fallback_aplicado: bool
    latencia_ms: int
    fecha_hora_solicitud: datetime
