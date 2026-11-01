from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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