"""Canal WebSocket del tablero: reenvía al navegador los eventos de triage de Redis.

El frontend se conecta a /api/v1/ws/tablero. Por cada cliente conectado se abre una
suscripción al canal de Redis `triage:eventos` y cada evento que llega se reenvía
tal cual (JSON, mismo formato del catálogo de eventos, sin PII).

Mensajes que recibe el cliente:
- Primero, un aviso de control `{"event_type": "conexion.lista", ...}` cuando la
  suscripción ya está activa. Desde ahí no se pierde ningún evento nuevo.
- Después, un mensaje por cada evento publicado (por ejemplo
  `triage.evaluacion.confirmada`).

Lo que el cliente envíe se ignora: el canal es solo de salida.

Pendiente: todavía no hay login, así que el canal no autentica. Al existir, hay que
validar el token y el origen de la conexión antes de aceptarla.
"""
import contextlib
import logging

import anyio
import redis
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.realtime import CANAL_TRIAGE, redis_url

router = APIRouter()
logger = logging.getLogger("meditriage.ws")

# 1011 = error interno del servidor (el canal no está disponible).
CODIGO_CANAL_NO_DISPONIBLE = 1011


async def _reenviar_eventos(websocket: WebSocket, pubsub, alcance: anyio.CancelScope) -> None:
    """Reenvía cada evento de Redis al cliente. Al terminar, detiene el otro trabajo."""
    try:
        async for mensaje in pubsub.listen():
            await websocket.send_text(mensaje["data"])
    except (WebSocketDisconnect, RuntimeError):
        pass  # el cliente ya se fue
    except (redis.RedisError, OSError) as exc:
        logger.warning("canal_tiempo_real_no_disponible", extra={"error_type": type(exc).__name__})
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=CODIGO_CANAL_NO_DISPONIBLE)
    finally:
        alcance.cancel()


async def _esperar_desconexion(websocket: WebSocket, alcance: anyio.CancelScope) -> None:
    """Espera a que el cliente se vaya; lo que envíe se ignora."""
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        alcance.cancel()


@router.websocket("/ws/tablero")
async def tablero(websocket: WebSocket):
    await websocket.accept()

    cliente = None
    pubsub = None
    try:
        cliente = aioredis.Redis.from_url(
            redis_url(), decode_responses=True, socket_connect_timeout=2
        )
        pubsub = cliente.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(CANAL_TRIAGE)
        await websocket.send_json({"event_type": "conexion.lista", "canal": CANAL_TRIAGE})

        # Un trabajo reenvía los eventos y el otro espera la desconexión del cliente.
        # Cuando cualquiera termina, cancela al otro.
        async with anyio.create_task_group() as grupo:
            grupo.start_soon(_reenviar_eventos, websocket, pubsub, grupo.cancel_scope)
            await _esperar_desconexion(websocket, grupo.cancel_scope)
    except WebSocketDisconnect:
        pass
    except (redis.RedisError, RuntimeError, OSError) as exc:
        logger.warning("canal_tiempo_real_no_disponible", extra={"error_type": type(exc).__name__})
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=CODIGO_CANAL_NO_DISPONIBLE)
    finally:
        # Cerrar la suscripción nunca debe tapar el error original ni quedar a medias.
        with anyio.CancelScope(shield=True), contextlib.suppress(Exception):
            if pubsub is not None:
                await pubsub.aclose()
            if cliente is not None:
                await cliente.aclose()