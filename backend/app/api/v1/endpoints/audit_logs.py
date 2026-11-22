"""Consulta de la bitácora de auditoría para el auditor (S10-6, US-05).

Solo lectura: no hay POST, PUT, PATCH ni DELETE (la tabla además es inmutable en la base).
Solo el rol auditor entra (403 al resto); la política RLS de registro_auditoria también
lo exige, así que si este chequeo faltara la base seguiría sin devolver nada a otros roles.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from psycopg.rows import dict_row

from app.core.auth import requiere_rol
from app.db import get_conn
from app.schemas.auditoria import AuditLogEntry, RegistroAlterado, VerificacionCadena

router = APIRouter(
    prefix="/audit-logs",
    tags=["Auditoría"],
    dependencies=[Depends(requiere_rol("auditor"))],
)

_COLUMNAS = """
    registro_id, episodio_id, decision_id, evento_tipo, usuario_id_actor,
    sugerencia_ia, prompt_enviado, decision_final, hay_discrepancia,
    hash_anterior, hash_actual, fecha_hora_evento
"""

_PRIMER_ROTO = """
    SELECT v.registro_id, v.motivo
    FROM verificar_cadena_auditoria() v
    JOIN registro_auditoria r ON r.registro_id = v.registro_id
    ORDER BY r.fecha_hora_evento, r.registro_id
    LIMIT 1
"""


@router.get("", response_model=list[AuditLogEntry])
def listar_audit_logs(
    episodio_id: Optional[UUID] = None,
    usuario_id: Optional[UUID] = None,
    hay_discrepancia: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    conn=Depends(get_conn),
):
    """Historial de auditoría, del más reciente al más antiguo."""
    condiciones: list[str] = []
    params: dict = {"skip": skip, "limit": limit}
    if episodio_id is not None:
        condiciones.append("episodio_id = %(episodio_id)s")
        params["episodio_id"] = episodio_id
    if usuario_id is not None:
        condiciones.append("usuario_id_actor = %(usuario_id)s")
        params["usuario_id"] = usuario_id
    if hay_discrepancia is not None:
        condiciones.append("hay_discrepancia = %(hay_discrepancia)s")
        params["hay_discrepancia"] = hay_discrepancia
    donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    # Las condiciones son texto fijo de arriba; los valores van siempre como parámetros.
    sql = (
        f"SELECT {_COLUMNAS} FROM registro_auditoria {donde} "
        "ORDER BY fecha_hora_evento DESC, registro_id DESC "
        "LIMIT %(limit)s OFFSET %(skip)s"
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/verificacion", response_model=VerificacionCadena)
def verificar_cadena_auditoria(conn=Depends(get_conn)):
    """Recorre la cadena de hashes y dice si es válida y cuál es el primer registro alterado."""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM registro_auditoria")
        total = cur.fetchone()[0]
        # verificar_cadena_auditoria() devuelve los registros rotos sin orden. Se ordenan
        # como la cadena (fecha, id): un registro alterado marca también al siguiente, así
        # que el primero es el que realmente se tocó.
        cur.execute(_PRIMER_ROTO)
        primero = cur.fetchone()
    if primero is None:
        return VerificacionCadena(valida=True, registros_verificados=total)
    return VerificacionCadena(
        valida=False,
        registros_verificados=total,
        primer_registro_alterado=RegistroAlterado(registro_id=primero[0], motivo=primero[1]),
    )
