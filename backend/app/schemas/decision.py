"""Esquemas de la decisión final de triage (confirmar o modificar el ESI de la IA)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ESI_MIN = 1
ESI_MAX = 5
# Si la enfermera cambia el nivel sugerido, debe explicar el motivo.
JUSTIFICACION_MIN_CARACTERES = 10


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nivel_esi_final: int = Field(
        strict=True,
        description=f"Nivel ESI definitivo ({ESI_MIN} a {ESI_MAX}).",
    )
    # Opcional si confirma lo que sugirió la IA; obligatoria si lo cambia
    # (esa regla depende del nivel sugerido, así que se valida en el endpoint).
    justificacion: Optional[str] = Field(default=None, max_length=1000)
    # Temporal hasta que exista el login: quién toma la decisión.
    usuario_id: Optional[UUID] = None

    @field_validator("nivel_esi_final")
    @classmethod
    def _rango_esi(cls, v: int) -> int:
        if not ESI_MIN <= v <= ESI_MAX:
            raise ValueError(f"El nivel ESI debe estar entre {ESI_MIN} y {ESI_MAX}.")
        return v

    @field_validator("justificacion")
    @classmethod
    def _justificacion_sin_vacios(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = " ".join(v.split())
        return v or None


class DecisionResponse(BaseModel):
    decision_id: UUID
    episodio_id: UUID
    nivel_esi_sugerido: int
    nivel_esi_final: int
    coincide_con_ia: bool
    modificado_manualmente: bool
    justificacion: Optional[str] = None
    usuario_id: Optional[UUID] = None
    fecha_hora_decision: datetime