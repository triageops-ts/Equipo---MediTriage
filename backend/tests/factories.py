"""Fábrica de datos sintéticos para pruebas en MediTriage (S09-5)."""

from datetime import date
from typing import Any
import uuid

ROLES_VALIDOS = ("enfermero", "medico", "auditor")


def calcular_dv_rut(cuerpo: int) -> str:
    """Calcula el dígito verificador chileno (módulo 11) para un entero positivo."""
    if not isinstance(cuerpo, int) or isinstance(cuerpo, bool) or cuerpo <= 0:
        raise ValueError("El cuerpo del RUT debe ser un entero positivo")

    suma = 0
    multiplicador = 2

    for digito in reversed(str(cuerpo)):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1

    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def formatear_rut(cuerpo: int, dv: str, con_puntos: bool = True) -> str:
    """Formatea un RUT como '11.111.111-1' o canónico '11111111-1'."""
    dv_limpio = dv.strip().upper()
    if not con_puntos:
        return f"{cuerpo}-{dv_limpio}"

    cuerpo_con_puntos = f"{cuerpo:,}".replace(",", ".")
    return f"{cuerpo_con_puntos}-{dv_limpio}"


def generar_rut_valido(cuerpo: int = 90000001, con_puntos: bool = True) -> str:
    """Genera un RUT chileno sintético con dígito verificador módulo 11 válido."""
    dv = calcular_dv_rut(cuerpo)
    return formatear_rut(cuerpo=cuerpo, dv=dv, con_puntos=con_puntos)


def signos_vitales_por_esi(nivel_esi: int) -> dict[str, Any]:
    """Devuelve signos vitales sintéticos válidos por nivel ESI (1 a 5)."""
    perfiles: dict[int, dict[str, Any]] = {
        1: {
            "presion_sistolica": 78,
            "presion_diastolica": 45,
            "frecuencia_cardiaca": 145,
            "frecuencia_respiratoria": 32,
            "temperatura": 35.4,
            "saturacion_oxigeno": 84,
            "escala_dolor": 10,
            "nivel_conciencia": "alerta",
        },
        2: {
            "presion_sistolica": 92,
            "presion_diastolica": 58,
            "frecuencia_cardiaca": 118,
            "frecuencia_respiratoria": 24,
            "temperatura": 38.9,
            "saturacion_oxigeno": 90,
            "escala_dolor": 8,
            "nivel_conciencia": "alerta",
        },
        3: {
            "presion_sistolica": 128,
            "presion_diastolica": 80,
            "frecuencia_cardiaca": 96,
            "frecuencia_respiratoria": 18,
            "temperatura": 37.8,
            "saturacion_oxigeno": 95,
            "escala_dolor": 6,
            "nivel_conciencia": "alerta",
        },
        4: {
            "presion_sistolica": 120,
            "presion_diastolica": 76,
            "frecuencia_cardiaca": 80,
            "frecuencia_respiratoria": 15,
            "temperatura": 36.8,
            "saturacion_oxigeno": 98,
            "escala_dolor": 4,
            "nivel_conciencia": "alerta",
        },
        5: {
            "presion_sistolica": 118,
            "presion_diastolica": 74,
            "frecuencia_cardiaca": 72,
            "frecuencia_respiratoria": 14,
            "temperatura": 36.6,
            "saturacion_oxigeno": 99,
            "escala_dolor": 1,
            "nivel_conciencia": "alerta",
        },
    }

    if nivel_esi not in perfiles:
        raise ValueError("El nivel ESI debe ser un entero entre 1 y 5")

    return dict(perfiles[nivel_esi])


def usuario_por_rol(rol: str = "enfermero", indice: int = 1) -> dict[str, Any]:
    """Genera datos sintéticos de usuario para los roles del sistema."""
    rol_normalizado = rol.strip().lower()
    if rol_normalizado not in ROLES_VALIDOS:
        raise ValueError(f"Rol no válido '{rol}'. Roles permitidos: {', '.join(ROLES_VALIDOS)}")

    return {
        "usuario_id": str(uuid.uuid4()),
        "email": f"{rol_normalizado}.test{indice}@meditriage.test",
        "password": "Demo-2026!",
        "rol": rol_normalizado,
    }


def paciente_sintetico(
    cuerpo_rut: int = 90000001,
    con_puntos: bool = True,
    name: str = "Paciente Sintetico",
    has_consent: bool = True,
    consent_version: str = "1.0",
    birth_date: date | None = None,
    email: str | None = None,
    biological_sex: str | None = None,
) -> dict[str, Any]:
    """Construye un payload sintético de paciente compatible con PatientInput."""
    payload: dict[str, Any] = {
        "rut": generar_rut_valido(cuerpo=cuerpo_rut, con_puntos=con_puntos),
        "name": name,
        "has_consent": has_consent,
        "consent_version": consent_version,
    }
    if birth_date is not None:
        payload["birth_date"] = birth_date
    if email is not None:
        payload["email"] = email
    if biological_sex is not None:
        payload["biological_sex"] = biological_sex
    return payload
