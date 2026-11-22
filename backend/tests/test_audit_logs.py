"""GET /audit-logs y /audit-logs/verificacion: roles, filtros y paginación (sin base de datos).

La conexión es falsa: se comprueba el SQL y los parámetros que se le piden, y la forma
de la respuesta. El comportamiento real contra Postgres está en test_audit_logs_db.py.
"""
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import crear_token
from app.db import get_conn
from app.main import app

EP = uuid.uuid4()
ACTOR = uuid.uuid4()


class _Cursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.conn.consultas.append((" ".join(sql.split()), params))
        self.ultima = " ".join(sql.split())

    def fetchall(self):
        return self.conn.filas

    def fetchone(self):
        if "count(*)" in self.ultima:
            return (self.conn.total,)
        return self.conn.primer_roto


class _Conn:
    def __init__(self, filas=(), total=0, primer_roto=None):
        self.filas = list(filas)
        self.total = total
        self.primer_roto = primer_roto
        self.consultas = []

    def cursor(self, **kwargs):
        return _Cursor(self)


def _fila(**extra):
    base = {
        "registro_id": uuid.uuid4(), "episodio_id": EP, "decision_id": None,
        "evento_tipo": "triage.override.ejecutado", "usuario_id_actor": ACTOR,
        "sugerencia_ia": 3, "prompt_enviado": None, "decision_final": 2,
        "hay_discrepancia": True, "hash_anterior": "0" * 64, "hash_actual": "a" * 64,
        "fecha_hora_evento": datetime(2026, 11, 1, 10, 0, 0),
    }
    base.update(extra)
    return base


def _con(conn, rol="auditor"):
    app.dependency_overrides[get_conn] = lambda: conn
    cliente = TestClient(app)
    token, _ = crear_token(uuid.uuid4(), rol)
    cliente.headers["Authorization"] = f"Bearer {token}"
    return cliente


@pytest.fixture(autouse=True)
def _limpiar():
    yield
    app.dependency_overrides.pop(get_conn, None)


@pytest.mark.parametrize("ruta", ["/api/v1/audit-logs", "/api/v1/audit-logs/verificacion"])
def test_sin_sesion_401(ruta):
    app.dependency_overrides[get_conn] = lambda: _Conn()
    assert TestClient(app).get(ruta).status_code == 401


@pytest.mark.parametrize("rol", ["enfermero", "medico"])
@pytest.mark.parametrize("ruta", ["/api/v1/audit-logs", "/api/v1/audit-logs/verificacion"])
def test_otros_roles_403(rol, ruta):
    conn = _Conn()
    assert _con(conn, rol).get(ruta).status_code == 403
    assert conn.consultas == []  # ni siquiera se consulta la base


def test_auditor_lista_registros():
    conn = _Conn([_fila()])
    r = _con(conn).get("/api/v1/audit-logs")
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["hay_discrepancia"] is True
    assert cuerpo[0]["sugerencia_ia"] == 3 and cuerpo[0]["decision_final"] == 2


def test_sin_filtros_usa_paginacion_por_defecto_y_orden_reciente():
    conn = _Conn()
    _con(conn).get("/api/v1/audit-logs")
    sql, params = conn.consultas[0]
    assert "WHERE" not in sql
    assert "ORDER BY fecha_hora_evento DESC, registro_id DESC" in sql
    assert params == {"skip": 0, "limit": 20}


def test_filtros_se_pasan_como_parametros():
    conn = _Conn()
    uid = uuid.uuid4()
    _con(conn).get(
        f"/api/v1/audit-logs?episodio_id={EP}&usuario_id={uid}&hay_discrepancia=true&skip=40&limit=10"
    )
    sql, params = conn.consultas[0]
    assert "episodio_id = %(episodio_id)s" in sql
    assert "usuario_id_actor = %(usuario_id)s" in sql
    assert "hay_discrepancia = %(hay_discrepancia)s" in sql
    assert params["episodio_id"] == EP and params["usuario_id"] == uid
    assert params["hay_discrepancia"] is True
    assert params["skip"] == 40 and params["limit"] == 10
    assert str(EP) not in sql  # nunca se concatena un valor en el SQL


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "skip=-1", "episodio_id=no-es-uuid", "hay_discrepancia=quizas"],
)
def test_parametros_invalidos_422(query):
    assert _con(_Conn()).get(f"/api/v1/audit-logs?{query}").status_code == 422


def test_verificacion_cadena_integra():
    r = _con(_Conn(total=5)).get("/api/v1/audit-logs/verificacion")
    assert r.status_code == 200
    assert r.json() == {"valida": True, "registros_verificados": 5, "primer_registro_alterado": None}


def test_verificacion_cadena_rota_informa_el_primer_registro():
    rid = uuid.uuid4()
    conn = _Conn(total=5, primer_roto=(rid, "hash_actual no coincide con el contenido del registro"))
    cuerpo = _con(conn).get("/api/v1/audit-logs/verificacion").json()
    assert cuerpo["valida"] is False
    assert cuerpo["primer_registro_alterado"]["registro_id"] == str(rid)
    assert "hash_actual" in cuerpo["primer_registro_alterado"]["motivo"]
    assert "ORDER BY r.fecha_hora_evento, r.registro_id" in conn.consultas[1][0]


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_no_hay_escritura_ni_borrado(metodo):
    r = getattr(_con(_Conn()), metodo)("/api/v1/audit-logs")
    assert r.status_code == 405
