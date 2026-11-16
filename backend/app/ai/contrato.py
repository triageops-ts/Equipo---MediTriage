"""Contrato de datos clínico -> IA (Tarjeta S09-4).

Define EXACTAMENTE qué recibe la IA y qué devuelve. La explicación completa, con la
lista de campos prohibidos y un ejemplo, está en docs/data/contrato-ia.md.

Regla de oro: a la IA solo llegan datos clínicos codificados. `extra="forbid"` hace que
un campo que no está en el contrato (rut, nombre, correo, teléfono, previsión,
fecha de nacimiento exacta, ids de paciente...) se rechace con un error en vez de
viajar al proveedor sin que nadie lo note.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.sanitizer import sanitize_symptoms_text
from app.schemas.triage import SignosVitalesInput, SintomaInput

VERSION_CONTRATO = "1.0"


class EntradaIA(BaseModel):
    """Lo único que puede recibir la IA."""

    model_config = ConfigDict(extra="forbid")

    # Edad en años cumplidos, no la fecha de nacimiento (es cuasi-identificador).
    edad_anios: int = Field(ge=0, le=120, strict=True)
    sexo_biologico: Optional[Literal["masculino", "femenino"]] = None
    signos_vitales: SignosVitalesInput
    sintomas: list[SintomaInput] = Field(default_factory=list, max_length=30)
    # Texto libre del paciente. Se vuelve a sanitizar aquí por seguridad: aunque quien
    # llame se olvide, el RUT, el correo y el teléfono nunca salen hacia la IA.
    motivo_consulta: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("motivo_consulta")
    @classmethod
    def _sanitizar_motivo(cls, v):
        if v is None:
            return None
        v = " ".join(sanitize_symptoms_text(v).split())
        return v or None


class SalidaIA(BaseModel):
    """Lo que debe devolver el modelo (JSON). Se valida antes de usarse."""

    # Las claves de más se ignoran; las que faltan o están fuera de rango son error.
    model_config = ConfigDict(extra="ignore")

    nivel_esi: int = Field(ge=1, le=5, strict=True)
    justificacion: str = Field(min_length=10, max_length=600)


class ClasificacionIA(BaseModel):
    """Resultado que recibe el resto del backend, venga de Claude o del respaldo.

    Los nombres coinciden con la tabla clasificacion_ia y con los eventos
    ia.clasificacion.sugerida / triage.clasificacion.respaldo_aplicada del catálogo.
    """

    nivel_esi_sugerido: int = Field(ge=1, le=5)
    justificacion: str
    modelo_usado: str
    latencia_ms: int = Field(ge=0)
    fallback_aplicado: bool
