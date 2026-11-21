"""Esquemas de la cola priorizada de triage (S10-3).

La cola la ven el tablero médico y la sala de espera, así que nunca lleva datos
personales: ni RUT, ni nombre, ni fecha de nacimiento, ni contactos. Del paciente
solo viaja su id interno, la edad (calculada) y el sexo biológico.
Coincide con `ColaTriageItem` y `PatientSummary` de api/openapi.yaml.
"""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EstadoEpisodio = Literal["en_espera", "en_atencion", "cerrado"]

# Sin filtro de estado se muestran los episodios que siguen abiertos.
ESTADOS_ACTIVOS: tuple[str, ...] = ("en_espera", "en_atencion")

LIMIT_POR_DEFECTO = 20
LIMIT_MAXIMO = 100


class PatientSummary(BaseModel):
    """Subconjunto seguro del paciente (sin RUT, nombre ni datos de contacto)."""

    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    age: Optional[int] = Field(
        default=None,
        ge=0,
        le=130,
        description="Edad en años. Nula si el paciente no tiene fecha de nacimiento.",
    )
    biological_sex: Optional[Literal["male", "female"]] = None


class ColaTriageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episodio_id: UUID
    patient: PatientSummary
    estado: EstadoEpisodio
    nivel_esi_sugerido: Optional[int] = Field(
        default=None, ge=1, le=5, description="Nivel sugerido por la IA. Nulo si aún no se evalúa."
    )
    nivel_esi_final: Optional[int] = Field(
        default=None, ge=1, le=5, description="Nivel definitivo. Nulo mientras no hay decisión."
    )
    fecha_hora_ingreso: datetime
    minutos_espera: int = Field(ge=0)
