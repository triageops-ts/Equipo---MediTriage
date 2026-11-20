"""GET /triage/cola contra una base real (S10-3).

Se omite sin DATABASE_URL y APP_ENCRYPTION_KEY. Crea 20 episodios con niveles ESI y
tiempos de ingreso conocidos y comprueba que la cola los devuelve en el orden clínico:
ESI ascendente y, a igual nivel, el que lleva más tiempo esperando. Los episodios sin
nivel van al final.

La base puede tener episodios de otras pruebas, así que se recorre la cola completa
(página por página) y se compara solo el orden relativo de los 20 episodios propios.
"""
import os

import psycopg
import pytest

from test_decision_db import _cabecera_enfermero, _episodio, client

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)

URL = "/api/v1/triage/cola"

# etiqueta: (nivel sugerido por la IA, nivel final de la enfermera, minutos esperando)
EPISODIOS = {
    "e01": (1, None, 10),
    "e02": (1, None, 45),
    "e03": (4, 1, 2),      # la enfermera subió la urgencia: cuenta como ESI 1
    "e04": (2, None, 60),
    "e05": (3, 2, 15),
    "e06": (2, None, 5),
    "e07": (3, None, 90),
    "e08": (3, None, 20),
    "e09": (5, 3, 100),
    "e10": (4, None, 70),
    "e11": (4, None, 25),
    "e12": (5, None, 300),
    "e13": (5, None, 30),
    "e14": (2, 4, 400),    # la enfermera bajó la urgencia: cuenta como ESI 4
    "e15": (None, None, 500),  # aún sin evaluar
    "e16": (None, None, 50),
    "e17": (3, None, 55),
    "e18": (1, None, 3),
    "e19": (4, None, 8),
    "e20": (5, None, 1),
}

# Escrito a mano (no calculado) para que la prueba no repita la lógica del endpoint.
ORDEN_ESPERADO = [
    "e02", "e01", "e18", "e03",          # ESI 1
    "e04", "e05", "e06",                 # ESI 2
    "e09", "e07", "e17", "e08",          # ESI 3
    "e14", "e10", "e11", "e19",          # ESI 4
    "e12", "e13", "e20",                 # ESI 5
    "e15", "e16",                        # sin nivel
]


def _admin():
    return psycopg.connect(os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"])


def _cabecera_medico() -> dict:
    from app.core.security import crear_token

    with _admin() as conn:
        fila = conn.execute(
            "SELECT usuario_id FROM usuario_staff WHERE rol = 'medico' AND activo LIMIT 1"
        ).fetchone()
    if not fila:
        pytest.skip("no hay un médico activo en usuario_staff")
    return {"Authorization": f"Bearer {crear_token(fila[0], 'medico')[0]}"}


@pytest.fixture(scope="module")
def cola_de_prueba() -> dict[str, str]:
    """Crea los 20 episodios y devuelve {etiqueta: episodio_id}."""
    ids = {}
    for etiqueta, (sugerido, final, minutos) in EPISODIOS.items():
        ep = _episodio(sugerido=sugerido)
        ids[etiqueta] = ep
        with _admin() as conn:
            conn.execute(
                "UPDATE episodio_triage SET fecha_hora_ingreso = "
                "(now() AT TIME ZONE 'UTC') - make_interval(mins => %s) WHERE episodio_id = %s",
                (minutos, ep),
            )
            if final is not None:
                conn.execute(
                    """
                    INSERT INTO decision_clinica
                        (decision_id, episodio_id, nivel_esi_final, coincide_con_ia,
                         justificacion, fecha_hora_decision)
                    VALUES (gen_random_uuid(), %s, %s, false,
                            'Ajuste clínico de prueba.', now() AT TIME ZONE 'UTC')
                    """,
                    (ep, final),
                )

    # Un paciente con fecha de nacimiento y sexo, para revisar edad y sexo en la respuesta.
    with _admin() as conn:
        conn.execute(
            "UPDATE paciente SET fecha_nacimiento = '1980-01-01', sexo_biologico = 'femenino' "
            "WHERE paciente_id = (SELECT paciente_id FROM episodio_triage WHERE episodio_id = %s)",
            (ids["e01"],),
        )
    return ids


def _cola_completa(cabecera: dict, **filtros) -> list[dict]:
    """Recorre todas las páginas de la cola."""
    items, skip = [], 0
    while True:
        r = client.get(URL, headers=cabecera, params={**filtros, "skip": skip, "limit": 100})
        assert r.status_code == 200, r.text
        pagina = r.json()
        items += pagina
        if len(pagina) < 100:
            return items
        skip += 100


def _vigente(item: dict):
    return item["nivel_esi_final"] or item["nivel_esi_sugerido"]


def test_orden_de_los_20_episodios(cola_de_prueba):
    por_id = {v: k for k, v in cola_de_prueba.items()}
    cola = _cola_completa(_cabecera_medico())
    propios = [por_id[i["episodio_id"]] for i in cola if i["episodio_id"] in por_id]
    assert propios == ORDEN_ESPERADO

    item = {i["episodio_id"]: i for i in cola}
    for etiqueta, (sugerido, final, minutos) in EPISODIOS.items():
        fila = item[cola_de_prueba[etiqueta]]
        assert fila["nivel_esi_sugerido"] == sugerido
        assert fila["nivel_esi_final"] == final
        assert fila["estado"] == "en_espera"
        assert fila["minutos_espera"] >= minutos


def test_toda_la_cola_respeta_el_orden(cola_de_prueba):
    cola = _cola_completa(_cabecera_medico())
    claves = [
        (_vigente(i) is None, _vigente(i) or 0, i["fecha_hora_ingreso"]) for i in cola
    ]
    assert claves == sorted(claves)


def test_sin_rut_ni_nombre(cola_de_prueba):
    r = client.get(URL, headers=_cabecera_medico(), params={"limit": 100})
    assert r.status_code == 200
    assert "Ana Soto" not in r.text  # nombre que usan los pacientes de prueba
    for item in r.json():
        assert set(item) == {
            "episodio_id", "patient", "estado", "nivel_esi_sugerido",
            "nivel_esi_final", "fecha_hora_ingreso", "minutos_espera",
        }
        assert set(item["patient"]) == {"patient_id", "age", "biological_sex"}


def test_edad_y_sexo_del_paciente(cola_de_prueba):
    cola = _cola_completa(_cabecera_medico(), nivel_esi=1)
    (fila,) = [i for i in cola if i["episodio_id"] == cola_de_prueba["e01"]]
    assert fila["patient"]["biological_sex"] == "female"
    assert 40 <= fila["patient"]["age"] <= 130


def test_filtro_nivel_esi_usa_el_nivel_vigente(cola_de_prueba):
    por_id = {v: k for k, v in cola_de_prueba.items()}
    cola = _cola_completa(_cabecera_medico(), nivel_esi=1)
    assert all(_vigente(i) == 1 for i in cola)
    # e03 tiene sugerido 4 pero final 1: entra. e14 tiene sugerido 2 pero final 4: no entra.
    assert [por_id[i["episodio_id"]] for i in cola if i["episodio_id"] in por_id] == [
        "e02", "e01", "e18", "e03",
    ]


def test_filtro_estado(cola_de_prueba):
    propios = set(cola_de_prueba.values())
    en_espera = {i["episodio_id"] for i in _cola_completa(_cabecera_medico(), estado="en_espera")}
    cerrados = _cola_completa(_cabecera_medico(), estado="cerrado")
    assert propios <= en_espera
    assert all(i["estado"] == "cerrado" for i in cerrados)
    assert not propios & {i["episodio_id"] for i in cerrados}


def test_paginacion_skip_y_limit(cola_de_prueba):
    cab = _cabecera_medico()
    todo = client.get(URL, headers=cab, params={"limit": 10}).json()
    p1 = client.get(URL, headers=cab, params={"skip": 0, "limit": 5}).json()
    p2 = client.get(URL, headers=cab, params={"skip": 5, "limit": 5}).json()
    assert len(todo) == 10
    assert [i["episodio_id"] for i in p1 + p2] == [i["episodio_id"] for i in todo]


def test_enfermero_tambien_puede_ver_la_cola(cola_de_prueba):
    r = client.get(URL, headers=_cabecera_enfermero())
    assert r.status_code == 200


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"skip": -1}, {"nivel_esi": 6}, {"estado": "otro"}]
)
def test_parametros_invalidos_422(params):
    r = client.get(URL, headers=_cabecera_medico(), params=params)
    assert r.status_code == 422
