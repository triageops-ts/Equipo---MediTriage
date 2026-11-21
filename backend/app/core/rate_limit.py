"""Límite de peticiones (rate limiting) para /auth/login y /triage/* (S11-1).

- /auth/login: por IP del cliente (todavía no hay usuario). Frena la fuerza bruta de contraseñas.
- /triage/*:   por usuario del token (varios enfermeros pueden compartir la IP del hospital).

Al superar el límite se responde 429 con el header `Retry-After` (segundos) y el cuerpo
problem+json de siempre (lo arma el manejador de HTTPException de app/main.py).

Configuración (variables de entorno, se leen en cada petición):
    RATE_LIMIT_ENABLED   "false" lo desactiva (por ejemplo, para pruebas de carga). Por defecto activo.
    RATE_LIMIT_LOGIN     por defecto "10/minute"
    RATE_LIMIT_TRIAGE    por defecto "120/minute"
    TRUSTED_PROXY_HOPS   cuántos proxies de confianza hay delante (Ingress, rewrite de Next).
                         0 (por defecto): se usa la IP de la conexión y se ignora X-Forwarded-For,
                         porque el cliente puede escribir ese header a mano.

Formato de los límites: "<cantidad>/<periodo>", con periodo second, minute, hour o day.

Limitación conocida: los contadores viven en la memoria de cada proceso. Con varios workers o
réplicas (HPA), el límite efectivo es el límite multiplicado por la cantidad de procesos.
"""
import logging
import math
import os
import threading
import time
from collections import deque

from fastapi import Depends, HTTPException, Request, status

from app.core.auth import usuario_actual
from app.core.security import Usuario

logger = logging.getLogger("meditriage.rate_limit")

LIMITE_LOGIN_POR_DEFECTO = "10/minute"
LIMITE_TRIAGE_POR_DEFECTO = "120/minute"

_PERIODOS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def parsear_limite(texto: str) -> tuple[int, int]:
    """'10/minute' -> (10, 60). Lanza ValueError si el formato no es válido."""
    cantidad, separador, periodo = texto.strip().partition("/")
    periodo = periodo.strip().lower().removesuffix("s")
    if not separador or periodo not in _PERIODOS:
        raise ValueError(f"Límite inválido: {texto!r}. Use por ejemplo '10/minute'.")
    n = int(cantidad)
    if n < 1:
        raise ValueError(f"Límite inválido: {texto!r}. La cantidad debe ser al menos 1.")
    return n, _PERIODOS[periodo]


class LimitadorMemoria:
    """Ventana deslizante: guarda el instante de cada petición aceptada por clave."""

    def __init__(self, reloj=time.monotonic):
        self._reloj = reloj
        self._lock = threading.Lock()  # los endpoints síncronos corren en varios hilos
        self._peticiones: dict[str, deque[float]] = {}
        self._ventana_max = 0
        self._ultima_limpieza = reloj()

    def intentar(self, clave: str, limite: int, ventana: int) -> float | None:
        """Registra la petición. None si se acepta; si no, los segundos que faltan para poder."""
        ahora = self._reloj()
        with self._lock:
            self._limpiar(ahora, ventana)
            marcas = self._peticiones.setdefault(clave, deque())
            while marcas and marcas[0] <= ahora - ventana:
                marcas.popleft()
            if len(marcas) >= limite:
                return marcas[0] + ventana - ahora
            marcas.append(ahora)
            return None

    def reiniciar(self) -> None:
        with self._lock:
            self._peticiones.clear()

    def _limpiar(self, ahora: float, ventana: int) -> None:
        # Borra las claves sin peticiones recientes para que la memoria no crezca sin fin
        # (por ejemplo, con muchas IP distintas probando el login).
        self._ventana_max = max(self._ventana_max, ventana)
        if ahora - self._ultima_limpieza < self._ventana_max:
            return
        self._ultima_limpieza = ahora
        vencidas = [
            k for k, m in self._peticiones.items() if not m or m[-1] <= ahora - self._ventana_max
        ]
        for k in vencidas:
            del self._peticiones[k]


limitador = LimitadorMemoria()


def limite_activo() -> bool:
    return os.environ.get("RATE_LIMIT_ENABLED", "true").strip().lower() not in ("0", "false", "no")


def _saltos_proxy() -> int:
    try:
        return max(0, int(os.environ.get("TRUSTED_PROXY_HOPS", "0")))
    except ValueError:
        return 0


def ip_cliente(request: Request) -> str:
    """IP del cliente. Solo se lee X-Forwarded-For si hay proxies de confianza configurados.

    Cada proxy agrega al final la IP de quien le habló, así que con N proxies de confianza
    la IP real es la N-ésima desde la derecha (las de la izquierda las puede inventar el cliente).
    """
    saltos = _saltos_proxy()
    if saltos:
        reenviadas = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
        reenviadas = [p for p in reenviadas if p]
        if len(reenviadas) >= saltos:
            return reenviadas[-saltos]
    return request.client.host if request.client else "desconocido"


def _aplicar(regla: str, clave: str, variable: str, por_defecto: str) -> None:
    if not limite_activo():
        return
    limite, ventana = parsear_limite(os.environ.get(variable, por_defecto))
    espera = limitador.intentar(f"{regla}:{clave}", limite, ventana)
    if espera is None:
        return
    segundos = max(1, math.ceil(espera))
    # Sin IP ni id de usuario en el log (datos personales).
    logger.warning("rate_limit_excedido", extra={"limite": regla})
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"Demasiadas peticiones. Intente nuevamente en {segundos} segundos.",
        headers={"Retry-After": str(segundos)},
    )


def limite_login(request: Request) -> None:
    """Dependencia de POST /auth/login: límite por IP."""
    _aplicar("login", f"ip:{ip_cliente(request)}", "RATE_LIMIT_LOGIN", LIMITE_LOGIN_POR_DEFECTO)


def limite_triage(usuario: Usuario = Depends(usuario_actual)) -> None:
    """Dependencia del router /triage: límite por usuario autenticado."""
    _aplicar(
        "triage", f"usuario:{usuario.usuario_id}", "RATE_LIMIT_TRIAGE", LIMITE_TRIAGE_POR_DEFECTO
    )
