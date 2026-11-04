"""Esquemas del formulario clínico de triage (signos vitales).

Los rangos son los de `SymptomsInput` en api/openapi.yaml. Un valor fuera de
rango se rechaza con 422 antes de guardarse o de llegar a la IA.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

NIVELES_CONCIENCIA = ("alerta", "verbal", "dolor", "inconsciente")

# campo: (mínimo, máximo, unidad)
RANGOS = {
    "presion_sistolica": (40, 260, "mmHg"),
    "presion_diastolica": (20, 200, "mmHg"),
    "frecuencia_cardiaca": (20, 300, "latidos por minuto"),
    "frecuencia_respiratoria": (5, 80, "respiraciones por minuto"),
    "temperatura": (30.0, 43.0, "°C"),
    "saturacion_oxigeno": (0, 100, "%"),
    "escala_dolor": (0, 10, "puntos"),
}


def _campo(nombre: str, descripcion: str, **kw):
    lo, hi, unidad = RANGOS[nombre]
    return Field(
        strict=True,  # un "98" (texto) o un 98.5 en un campo entero se rechaza
        description=f"{descripcion} ({unidad}). Rango válido: {lo} a {hi}.",
        json_schema_extra={"minimum": lo, "maximum": hi},
        **kw,
    )


class SignosVitalesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presion_sistolica: int = _campo("presion_sistolica", "Presión sistólica")
    presion_diastolica: int = _campo("presion_diastolica", "Presión diastólica")
    frecuencia_cardiaca: int = _campo("frecuencia_cardiaca", "Pulso")
    frecuencia_respiratoria: int = _campo("frecuencia_respiratoria", "Frecuencia respiratoria")
    temperatura: float = _campo("temperatura", "Temperatura", allow_inf_nan=False)
    saturacion_oxigeno: int = _campo("saturacion_oxigeno", "Saturación de oxígeno (SpO2)")
    escala_dolor: int = _campo("escala_dolor", "Escala de dolor")
    nivel_conciencia: str = Field(description="alerta, verbal, dolor o inconsciente")

    @field_validator(*RANGOS)
    @classmethod
    def _rango_fisiologico(cls, v, info):
        lo, hi, unidad = RANGOS[info.field_name]
        if not (lo <= v <= hi):
            raise ValueError(
                f"Valor fuera de rango fisiológico: debe estar entre {lo} y {hi} {unidad}."
            )
        if info.field_name == "presion_diastolica":
            sistolica = info.data.get("presion_sistolica")
            if sistolica is not None and v >= sistolica:
                raise ValueError("La presión diastólica debe ser menor que la sistólica.")
        return v

    @field_validator("nivel_conciencia", mode="before")
    @classmethod
    def _nivel_conciencia(cls, v):
        if isinstance(v, str) and v.strip().lower() in NIVELES_CONCIENCIA:
            return v.strip().lower()
        raise ValueError("Debe ser uno de: " + ", ".join(NIVELES_CONCIENCIA) + ".")

class SintomaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo_sintoma: str = Field(
        min_length=1,
        description="Código del síntoma según catálogo clínico.",
    )
    severidad: str = Field(
        description="Severidad del síntoma: leve, moderada o severa.",
    )
    tiempo_evolucion_horas: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tiempo de evolución del síntoma en horas.",
    )

    @field_validator("codigo_sintoma")
    @classmethod
    def validar_codigo(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("El código del síntoma no puede estar vacío.")
        return v

    @field_validator("severidad", mode="before")
    @classmethod
    def validar_severidad(cls, v):
        if isinstance(v, str) and v.strip().lower() in (
            "leve", "moderada", "severa"
        ):
            return v.strip().lower()
        raise ValueError("La severidad debe ser leve, moderada o severa.")


class FormularioClinicoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID = Field(description="Paciente ya registrado (POST /patients).")
    # Temporal hasta que exista el login: quién registra el formulario.
    usuario_id: Optional[UUID] = None
    motivo_consulta: Optional[str] = Field(default=None, max_length=1000)
    signos_vitales: SignosVitalesInput
    sintomas: list[SintomaInput] = Field(default_factory=list)

    @field_validator("motivo_consulta")
    @classmethod
    def _motivo_sin_vacios(cls, v):
        if v is None:
            return None
        v = " ".join(v.split())
        return v or None


class FormularioClinicoResponse(BaseModel):
    episodio_id: UUID
    signos_vitales_id: UUID
    patient_id: UUID
    estado: str
    fecha_hora_ingreso: datetime
    signos_vitales: SignosVitalesInput