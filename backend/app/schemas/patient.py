from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.consent import CONSENT_VERSION_ACTUAL, CONSENT_VERSIONES_VALIDAS
from app.core.rut import RutInvalido, normalizar_rut

_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class PatientInput(BaseModel):
    rut: str
    name: str = Field(min_length=2, max_length=150)
    birth_date: Optional[date] = None
    biological_sex: Optional[Literal["male", "female"]] = None
    address: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=150, pattern=_EMAIL)
    has_consent: bool
    consent_version: str = CONSENT_VERSION_ACTUAL

    @field_validator("rut")
    @classmethod
    def _rut_modulo_11(cls, v: str) -> str:
        try:
            return normalizar_rut(v)
        except RutInvalido as e:
            raise ValueError(str(e)) from None

    @field_validator("name")
    @classmethod
    def _nombre_sin_espacios_extra(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("El nombre es obligatorio.")
        return v

    @field_validator("birth_date", mode="before")
    @classmethod
    def _fecha_tipo_valido(cls, v):
        if v is not None and not isinstance(v, (str, date)):
            raise ValueError("La fecha debe tener formato YYYY-MM-DD.")
        return v

    @field_validator("birth_date")
    @classmethod
    def _no_futura(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura.")
        return v

    @field_validator("has_consent")
    @classmethod
    def _consentimiento_obligatorio(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError(
                "Se requiere el consentimiento informado del paciente (has_consent=true)."
            )
        return v

    @field_validator("consent_version")
    @classmethod
    def _version_conocida(cls, v: str) -> str:
        if v not in CONSENT_VERSIONES_VALIDAS:
            validas = ", ".join(sorted(CONSENT_VERSIONES_VALIDAS))
            raise ValueError(
                f"Versión de consentimiento desconocida '{v}'. Versiones válidas: {validas}."
            )
        return v


class Patient(BaseModel):
    patient_id: UUID
    rut: str
    name: str
    birth_date: Optional[date] = None
    biological_sex: Optional[Literal["male", "female"]] = None
    has_consent: bool
    consent_id: UUID
    consent_version: str
    consent_accepted_at: datetime

class PatientFound(BaseModel):
    """Resultado de buscar un paciente por RUT (GET /patients?rut=...)."""

    patient_id: UUID
    rut: str  # formateado: 11.111.111-1
    name: str
    birth_date: Optional[date] = None
    biological_sex: Optional[Literal["male", "female"]] = None


class PatientUpdate(BaseModel):
    """Body de PATCH /patients/{patient_id}: corrige datos de un paciente ya registrado.

    Solo cambia los campos que vienen en el body. El RUT no se puede cambiar (identifica al
    paciente) y los campos desconocidos se rechazan con 422. birth_date y biological_sex
    aceptan null para dejar el dato vacío; name no.
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    birth_date: Optional[date] = None
    biological_sex: Optional[Literal["male", "female"]] = None

    @field_validator("name")
    @classmethod
    def _nombre_sin_espacios_extra(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("El nombre es obligatorio.")
        return v

    @field_validator("birth_date")
    @classmethod
    def _no_futura(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura.")
        return v

    @model_validator(mode="after")
    def _algo_que_cambiar(self) -> "PatientUpdate":
        if not self.model_fields_set:
            raise ValueError("Indique al menos un dato para actualizar.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("El nombre no puede quedar vacío.")
        return self
