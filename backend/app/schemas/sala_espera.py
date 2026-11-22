"""Esquema de la pantalla pública de la sala de espera (S11-10, US-04).

La ve cualquiera que esté en la sala, sin login. Por eso cada fila lleva solo un turno
anonimizado (ej. "A-12"), el nivel ESI, el estado, la posición y los tiempos.
Nunca RUT, nombre, patient_id ni episodio_id.
Coincide con `SalaEsperaEntry` de api/openapi.yaml.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cola import EstadoEpisodio

# El día del correlativo se cuenta en hora de Chile (la columna guarda UTC sin zona).
ZONA_HORARIA_TURNOS = "America/Santiago"

# Tope de filas: la pantalla es para un monitor, no un listado paginado.
MAX_FILAS_SALA = 100

# Tiempo objetivo de atención por nivel ESI, en minutos (el mismo que muestra la pantalla).
# El backlog deja el algoritmo como negociable: si cambia, cambiar también el contrato.
TIEMPO_OBJETIVO_MIN: dict[int, int] = {1: 0, 2: 15, 3: 60, 4: 120, 5: 180}


def formatear_turno(letra: str, numero: int) -> str:
    """Letra del día (A..Z, la calcula la consulta) y correlativo de llegada: "A-12"."""
    return f"{letra}-{numero}"


def tiempo_estimado(nivel_esi: Optional[int], estado: str, minutos_espera: int) -> Optional[int]:
    """Minutos que le quedan según el objetivo de su categoría.

    0 si ya está en atención o si ya cumplió el objetivo; None si aún no tiene nivel ESI.
    """
    if estado == "en_atencion":
        return 0
    if nivel_esi is None:
        return None
    return max(0, TIEMPO_OBJETIVO_MIN[nivel_esi] - minutos_espera)


class SalaEsperaEntry(BaseModel):
    # extra="forbid": si alguien agrega un campo con datos personales, falla en vez de salir.
    model_config = ConfigDict(extra="forbid")

    turno: str = Field(pattern=r"^[A-Z]-[0-9]+$", description="Turno anonimizado, ej. A-12.")
    nivel_esi: Optional[int] = Field(default=None, ge=1, le=5)
    estado: EstadoEpisodio
    posicion: Optional[int] = Field(
        default=None, ge=1, description="Lugar en la fila. Nulo si ya está en atención."
    )
    minutos_espera: int = Field(ge=0)
    tiempo_estimado_min: Optional[int] = Field(default=None, ge=0)
