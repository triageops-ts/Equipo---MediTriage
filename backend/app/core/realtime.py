"""Canal en tiempo real: eventos de triage por Redis Pub/Sub.

El backend publica un evento en el canal `triage:eventos` cuando ocurre algo que el
tablero debe mostrar (por ejemplo, al registrarse la decisión final). Quien esté
suscrito, como el WebSocket del tablero, lo recibe al instante.

Reglas:
- Los eventos siguen el formato de docs/data/event-catalog.md y no llevan PII:
  solo identificadores y el nivel ESI, nunca nombre, RUT ni texto clínico libre.
- Pub/Sub no guarda mensajes: si nadie está suscrito en ese momento, el evento se
  pierde. Es lo esperado para avisos en vivo (ver docs/adr/0004-datos-y-eventos.md).
- Publicar nunca debe romper la operación principal: si Redis falla, se registra un
  aviso en el log y la petición sigue (la decisión ya quedó guardada en Postgres).
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import redis

logger = logging.getLogger("meditriage.realtime")

CANAL_TRIAGE = "triage:eventos"
PRODUCTOR = "triage-service"
VERSION_EVENTO = "1.0"

# Eventos que se publican hoy (nombres del catálogo de eventos).
EVENTO_EVALUACION_CONFIRMADA = "triage.evaluacion.confirmada"

_cliente: Optional[redis.Redis] = None


def redis_url() -> str:
    url = os.environ.get("REDIS_URL")
    if not url:
        raise RuntimeError("Falta la variable de entorno REDIS_URL.")
    return url


def _cliente_redis() -> redis.Redis:
    """Un único cliente por proceso; el pool de conexiones lo maneja la librería."""
    global _cliente
    if _cliente is None:
        _cliente = redis.Redis.from_url(
            redis_url(), socket_connect_timeout=2, socket_timeout=2
        )
    return _cliente


def construir_evento(tipo: str, data: dict[str, Any]) -> dict[str, Any]:
    """Arma el sobre del evento (mismo formato que el catálogo de eventos)."""
    return {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "event_type": tipo,
        "version": VERSION_EVENTO,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": PRODUCTOR,
        "data": data,
    }


def publicar_evento(tipo: str, data: dict[str, Any]) -> bool:
    """Publica un evento en el canal de triage. Devuelve True si se publicó.

    No lanza excepciones por fallos de Redis: avisa en el log y devuelve False.
    """
    evento = construir_evento(tipo, data)
    try:
        _cliente_redis().publish(
            CANAL_TRIAGE, json.dumps(evento, ensure_ascii=False, default=str)
        )
    except (redis.RedisError, RuntimeError, OSError) as exc:
        logger.warning(
            "evento_no_publicado",
            extra={"evento": tipo, "error_type": type(exc).__name__},
        )
        return False
    return True