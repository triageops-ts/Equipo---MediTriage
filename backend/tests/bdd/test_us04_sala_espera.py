"""US-04 · Pantalla pública de sala de espera: los 3 escenarios de docs/scenarios (S11-11).

Usa una base real (se omite sin DATABASE_URL y APP_ENCRYPTION_KEY). Los episodios de las
pruebas 2 y 3 se crean en un día viejo y al azar para poder reconocerlos entre los demás
(tienen más de un millón de minutos de espera); en la prueba 1 el turno nuevo se reconoce
comparando la lista antes y después de crearlo.

Lo que NO se prueba aquí: que el navegador repita la consulta cada pocos segundos. No hay un
framework de pruebas del frontend; lo que sí se comprueba es que cada consulta devuelve el
estado actual (sin caché) y que la prioridad se mantiene tras los cambios.
"""
import os
import random
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from pytest_bdd import given, scenario, then, when

from app.api.v1.endpoints.sala_espera import MAX_FILAS_SALA
from app.schemas.sala_espera import TIEMPO_OBJETIVO_MIN
from tests.pii import buscar_pii
from tests.test_decision_db import SIGNOS, _episodio, _post, _rut_unico

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)

FEATURE = next((Path(__file__).resolve().parents[3] / "docs" / "scenarios").glob("US04_*.feature"))
URL = "/api/v1/sala-espera"
MUY_ANTIGUO = 1_000_000  # minutos: solo los episodios de estas pruebas esperan tanto
CAMPOS = {"turno", "nivel_esi", "estado", "posicion", "minutos_espera", "tiempo_estimado_min"}


def _admin():
    return psycopg.connect(os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"])


def _decision(episodio_id: str, nivel: int) -> None:
    with _admin() as conn:
        conn.execute(
            """
            INSERT INTO decision_clinica
                (decision_id, episodio_id, nivel_esi_final, coincide_con_ia,
                 justificacion, fecha_hora_decision)
            VALUES (gen_random_uuid(), %s, %s, false, 'Ajuste clínico de prueba.',
                    now() AT TIME ZONE 'UTC')
            """,
            (episodio_id, nivel),
        )


def _cambiar(episodio_id: str, estado: str) -> None:
    with _admin() as conn:
        conn.execute(
            "UPDATE episodio_triage SET estado = %s WHERE episodio_id = %s", (estado, episodio_id)
        )


def _episodio_en_dia_viejo(dia: datetime, minutos: int, esi: int) -> str:
    ep = _episodio(sugerido=esi)
    with _admin() as conn:
        conn.execute(
            "UPDATE episodio_triage SET fecha_hora_ingreso = %s WHERE episodio_id = %s",
            (dia + timedelta(minutes=minutos), ep),
        )
    _decision(ep, esi)
    return ep


@pytest.fixture
def limpieza():
    """Cierra al terminar los episodios que la prueba deja en la sala."""
    ids: list[str] = []
    yield ids
    if ids:
        with _admin() as conn:
            conn.execute(
                "UPDATE episodio_triage SET estado = 'cerrado' WHERE episodio_id = ANY(%s)", (ids,)
            )


@pytest.fixture
def estado_us04():
    return {}


def _sala(client):
    r = client.get(URL)  # sin token: la pantalla es pública
    assert r.status_code == 200, r.text
    assert "no-store" in r.headers["cache-control"]
    return r


def _propios(filas):
    return [f for f in filas if f["minutos_espera"] > MUY_ANTIGUO]


# ===================================================================================
# 🟢 Visualización de un turno anonimizado
# ===================================================================================


@scenario(str(FEATURE), "Visualización de un turno anonimizado (🟢)")
def test_us04_turno_anonimizado():
    """Escenario 🟢."""


@given("que un paciente tiene un turno registrado en el sistema")
def _turno_registrado(estado_us04, client, limpieza):
    estado_us04["antes"] = {f["turno"] for f in _sala(client).json()}
    estado_us04["episodio"] = _episodio(sugerido=4)
    limpieza.append(estado_us04["episodio"])


@given("su categorización ESI ha sido registrada")
def _esi_registrada(estado_us04):
    _decision(estado_us04["episodio"], 4)


@when("la pantalla pública consulta los turnos disponibles")
def _consulta(estado_us04, client):
    r = _sala(client)
    estado_us04["texto"] = r.text
    nuevos = [f for f in r.json() if f["turno"] not in estado_us04["antes"]]
    assert len(nuevos) == 1, "debería haber aparecido exactamente un turno nuevo"
    estado_us04["fila"] = nuevos[0]


@then("debe mostrar el identificador anonimizado del turno")
def _ver_turno(estado_us04):
    assert re.fullmatch(r"[A-Z]-[0-9]+", estado_us04["fila"]["turno"])


@then("debe mostrar su estado actual de atención")
def _ver_estado(estado_us04):
    assert estado_us04["fila"]["estado"] == "en_espera"
    assert estado_us04["fila"]["nivel_esi"] == 4
    assert estado_us04["fila"]["posicion"] >= 1


@then("debe mostrar el tiempo estimado de espera correspondiente")
def _ver_tiempo(estado_us04):
    fila = estado_us04["fila"]
    # Recién llegó: falta casi todo el objetivo de su categoría (ESI 4 = 120 min).
    esperado = max(0, TIEMPO_OBJETIVO_MIN[4] - fila["minutos_espera"])
    assert fila["tiempo_estimado_min"] == esperado
    assert 100 <= fila["tiempo_estimado_min"] <= TIEMPO_OBJETIVO_MIN[4]


@then("no debe mostrar el nombre completo ni el RUT del paciente.")
def _sin_nombre_ni_rut(estado_us04):
    assert "Ana Soto" not in estado_us04["texto"]  # nombre del paciente de prueba
    assert buscar_pii(estado_us04["texto"]) == []
    assert estado_us04["episodio"] not in estado_us04["texto"]


# ===================================================================================
# 🟡 Actualización simultánea de varios turnos
# ===================================================================================


@scenario(str(FEATURE), "Actualización simultánea de varios turnos (🟡)")
def test_us04_varios_turnos_cambian_a_la_vez():
    """Escenario 🟡."""


@given("que existen varios pacientes esperando atención")
def _varios_esperando(estado_us04, limpieza):
    # Día viejo y al azar entre 1990 y 2010, a las 15:00 UTC.
    estado_us04["dia"] = datetime(1990, 1, 1, 15, 0) + timedelta(days=random.randrange(7300))
    estado_us04["ids"] = {}


@given("sus turnos pertenecen a diferentes categorías ESI")
def _distintas_categorias(estado_us04, limpieza):
    # Llegan en este orden: A (ESI 3), B (ESI 2), C (ESI 1), D (ESI 2).
    for k, (etiqueta, esi) in enumerate([("A", 3), ("B", 2), ("C", 1), ("D", 2)]):
        ep = _episodio_en_dia_viejo(estado_us04["dia"], 10 * k, esi)
        estado_us04["ids"][etiqueta] = ep
        limpieza.append(ep)
    estado_us04["esi"] = {"A": 3, "B": 2, "C": 1, "D": 2}
    estado_us04["numero"] = {}


def _filas_propias(client):
    """Filas de la prueba, en el orden en que la sala las muestra, con su letra de turno."""
    filas = _propios(_sala(client).json())
    assert len({f["turno"].split("-")[0] for f in filas}) <= 1  # mismo día: misma letra
    return filas


@when("se actualiza el estado de uno o más pacientes")
def _cambian_a_la_vez(estado_us04, client):
    antes = _filas_propias(client)
    # Antes del cambio: C (ESI 1), B y D (ESI 2, B llegó antes), A (ESI 3).
    assert [f["nivel_esi"] for f in antes] == [1, 2, 2, 3]
    assert [f["estado"] for f in antes] == ["en_espera"] * 4
    # Dos cambios seguidos: C pasa a atención y B se cierra.
    _cambiar(estado_us04["ids"]["C"], "en_atencion")
    _cambiar(estado_us04["ids"]["B"], "cerrado")
    # La pantalla vuelve a consultar y recibe lo nuevo, sin recargar nada.
    estado_us04["filas"] = _filas_propias(client)


@then("la pantalla pública debe actualizar los turnos automáticamente")
def _se_actualiza(estado_us04, client):
    filas = estado_us04["filas"]
    assert len(filas) == 3  # B salió de la lista
    estados = sorted(f["estado"] for f in filas)
    assert estados == ["en_atencion", "en_espera", "en_espera"]
    # Cada consulta trae el estado vigente: no se sirve nada de caché.
    assert "no-store" in client.get(URL).headers["cache-control"]


@then("debe mantener el orden de atención correspondiente a la prioridad definida")
def _mantiene_orden(estado_us04, client):
    filas = estado_us04["filas"]
    assert [f["nivel_esi"] for f in filas] == [1, 2, 3]  # C (en atención), D, A
    assert [f["estado"] for f in filas] == ["en_atencion", "en_espera", "en_espera"]
    # La fila de espera se recalcula: C ya no espera y D va antes que A. (No se exige que sean
    # el 1.º y el 2.º de la fila: una base compartida puede tener otros pacientes esperando.)
    assert filas[0]["posicion"] is None
    assert 1 <= filas[1]["posicion"] < filas[2]["posicion"]
    # Toda la lista, no solo los turnos de la prueba, sigue ordenada por prioridad.
    todo = _sala(client).json()
    claves = [(f["nivel_esi"], -f["minutos_espera"]) for f in todo]
    assert claves == sorted(claves)
    assert len(todo) <= MAX_FILAS_SALA


@then("debe continuar mostrando únicamente identificadores anonimizados.")
def _solo_anonimos(estado_us04, client):
    r = _sala(client)
    assert buscar_pii(r.text) == []
    for f in r.json():
        assert set(f) == CAMPOS
        assert re.fullmatch(r"[A-Z]-[0-9]+", f["turno"])


# ===================================================================================
# 🔴 Intento de mostrar datos personales
# ===================================================================================


@scenario(str(FEATURE), "Intento de mostrar datos personales (🔴)")
def test_us04_datos_personales_excluidos():
    """Escenario 🔴."""


NOMBRE = "Valentina Rojas Pérez"
SINTOMA = "dolor torácico opresivo con irradiación al brazo"


@given("que existe información personal del paciente almacenada en el sistema")
def _hay_datos_personales(estado_us04, client, limpieza):
    estado_us04["rut"] = _rut_unico()
    p = _post(
        "/api/v1/patients",
        json={"rut": estado_us04["rut"], "name": NOMBRE, "has_consent": True},
    )
    assert p.status_code == 201, p.text
    estado_us04["patient_id"] = p.json()["patient_id"]
    f = _post(
        "/api/v1/triage/formulario",
        json={"patient_id": estado_us04["patient_id"], "signos_vitales": SIGNOS},
    )
    assert f.status_code == 201, f.text
    ep = f.json()["episodio_id"]
    limpieza.append(ep)
    estado_us04["episodio"] = ep
    with _admin() as conn:  # sugerencia de la IA con un texto clínico
        conn.execute(
            """
            INSERT INTO clasificacion_ia
                (clasificacion_id, episodio_id, token_correlacion_efimero, nivel_esi_sugerido,
                 tiempo_solicitud, tiempo_respuesta, modelo_usado, hash_datos_enviados_ia,
                 justificacion_ia)
            VALUES (%s, %s, %s, 2, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC',
                    'test', 'hash-de-prueba', %s)
            """,
            (uuid.uuid4(), ep, uuid.uuid4(), SINTOMA),
        )
    _decision(ep, 2)


@when("la pantalla pública solicita los datos necesarios para mostrar los turnos")
def _pide_la_sala(estado_us04, client):
    r = client.get(URL)  # sin token
    assert r.status_code == 200, r.text
    estado_us04["resp"] = r


@then("el sistema debe excluir el RUT, nombre completo y otros datos personales")
def _excluye_personales(estado_us04):
    texto = estado_us04["resp"].text
    rut = estado_us04["rut"]
    cuerpo = rut.replace(".", "").split("-")[0]
    for prohibido in (rut, rut.replace(".", ""), cuerpo, NOMBRE, "Valentina", "Rojas"):
        assert prohibido not in texto, f"la sala publica {prohibido!r}"
    assert estado_us04["patient_id"] not in texto
    assert buscar_pii(texto) == []


@then("debe mostrar únicamente el identificador público del turno")
def _solo_turno(estado_us04):
    filas = estado_us04["resp"].json()
    assert filas
    for f in filas:
        assert set(f) == CAMPOS
        assert re.fullmatch(r"[A-Z]-[0-9]+", f["turno"])
    assert estado_us04["episodio"] not in estado_us04["resp"].text


@then("no debe exponer información clínica del paciente.")
def _sin_clinica(estado_us04):
    texto = estado_us04["resp"].text.lower()
    assert SINTOMA.split()[0] not in texto and "torácico" not in texto
    for dato in ("presion", "frecuencia", "temperatura", "saturacion", "justificacion", "sintoma"):
        assert dato not in texto
    # Del nivel ESI solo se publica el final (decidido por enfermería), nada de la sugerencia de la IA.
    assert "sugerido" not in texto and "ia" not in set(estado_us04["resp"].json()[0])
