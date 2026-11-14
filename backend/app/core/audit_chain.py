"""Cadena de hashes de la bitácora `registro_auditoria` (solo librería estándar).

Cada registro guarda el hash del anterior (`hash_anterior`) y su propio hash
(`hash_actual`). Si alguien cambia o borra un registro viejo, la cadena deja de
cuadrar y `verificar_cadena` lo detecta.

OJO: esta es la definición del hash para los eventos que llegan del navegador.
Cuando se implemente la US-05 el equipo debe usar esta misma función (o
reemplazarla en un solo lugar) para que toda la tabla comparta una cadena.
"""
import hashlib
import json
from datetime import datetime
from typing import Any, Iterable, Optional
from uuid import UUID

# `hash_anterior` del primer registro de la tabla.
HASH_GENESIS = "0" * 64


def _canonico(valor: Any) -> str:
    # sort_keys + separadores fijos: el mismo contenido siempre da el mismo texto.
    return json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def calcular_hash(
    *,
    hash_anterior: str,
    evento_tipo: str,
    entidad_afectada: str,
    entidad_id: Optional[UUID],
    usuario_id: Optional[UUID],
    detalle: dict,
    fecha_hora_evento: datetime,
) -> str:
    contenido = _canonico(
        {
            "hash_anterior": hash_anterior,
            "evento_tipo": evento_tipo,
            "entidad_afectada": entidad_afectada,
            "entidad_id": str(entidad_id) if entidad_id else None,
            "usuario_id": str(usuario_id) if usuario_id else None,
            "detalle": detalle,
            "fecha_hora_evento": fecha_hora_evento.isoformat(),
        }
    )
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def verificar_cadena(registros: Iterable[dict]) -> Optional[int]:
    """Recibe los registros en orden cronológico.

    Devuelve None si la cadena está íntegra, o la posición (desde 0) del primer
    registro que no cuadra.
    """
    anterior = HASH_GENESIS
    for i, r in enumerate(registros):
        if r["hash_anterior"] != anterior:
            return i
        esperado = calcular_hash(
            hash_anterior=r["hash_anterior"],
            evento_tipo=r["evento_tipo"],
            entidad_afectada=r["entidad_afectada"],
            entidad_id=r["entidad_id"],
            usuario_id=r["usuario_id"],
            detalle=r["detalle_json"],
            fecha_hora_evento=r["fecha_hora_evento"],
        )
        if r["hash_actual"] != esperado:
            return i
        anterior = r["hash_actual"]
    return None