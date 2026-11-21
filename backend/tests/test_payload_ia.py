"""S09-8: auditoría del payload REAL que sale hacia Claude.

Solo se reemplaza el cliente HTTP de Anthropic por uno falso que guarda exactamente lo que
recibiría `messages.create` (system + messages). Todo lo demás es el código real: contrato,
sanitizador, ficha y cadena LangChain. Así se prueba lo que viaja, no lo que creemos que viaja.

- Las pruebas sin base corren siempre (también en CI).
- La prueba de punta a punta (POST /patients -> /triage/formulario -> /evaluate) se omite sin
  DATABASE_URL y APP_ENCRYPTION_KEY.
"""
import json
import os
from types import SimpleNamespace

import psycopg
import pytest

from app.ai import engine
from app.ai.contrato import EntradaIA

RUT = "19.876.543-2"
CORREO = "juan.perez@email.com"
TELEFONO = "+56912345678"
MOTIVO_CON_PII = (
    f"Dolor de cabeza hace 2 días. Mi RUT es {RUT}, escríbame a {CORREO} "
    f"o llámeme al {TELEFONO}"
)

SIGNOS = dict(
    presion_sistolica=120,
    presion_diastolica=80,
    frecuencia_cardiaca=80,
    frecuencia_respiratoria=16,
    temperatura=36.6,
    saturacion_oxigeno=98,
    escala_dolor=3,
    nivel_conciencia="alerta",
)

requiere_db = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("APP_ENCRYPTION_KEY")),
    reason="requiere DATABASE_URL y APP_ENCRYPTION_KEY",
)


class ClienteFalso:
    """Imita a anthropic.Anthropic: guarda cada llamada y responde un JSON válido."""

    def __init__(self):
        self.llamadas = []
        self.messages = self  # el motor llama a cliente.messages.create(...)

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        texto = json.dumps(
            {
                "nivel_esi": 4,
                "justificacion": "Signos vitales sin alteraciones y dolor leve; sin criterios de mayor urgencia.",
            }
        )
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)])

    def ultima(self) -> dict:
        assert self.llamadas, "la IA no fue llamada"
        return self.llamadas[-1]

    def payload(self) -> str:
        """Todo lo que viajó al proveedor, como un solo texto."""
        return json.dumps(self.ultima(), ensure_ascii=False)


@pytest.fixture
def cliente(monkeypatch):
    falso = ClienteFalso()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-falsa-de-pruebas")
    monkeypatch.setattr(engine, "_cliente_anthropic", lambda api_key, timeout_s: falso)
    return falso


def _entrada(motivo):
    return EntradaIA(
        edad_anios=40, sexo_biologico="femenino", signos_vitales=SIGNOS, motivo_consulta=motivo
    )


def test_payload_real_no_lleva_rut_correo_ni_telefono(cliente):
    engine.clasificar(_entrada(MOTIVO_CON_PII))
    payload = cliente.payload()

    for dato in (RUT, "19876543", CORREO, TELEFONO, "12345678"):
        assert dato not in payload, f"'{dato}' viajó a la IA"
    # El motivo sí viaja, pero enmascarado.
    assert "Dolor de cabeza" in payload
    assert "[RUT OCULTO]" in payload
    assert "[EMAIL OCULTO]" in payload
    assert "[TELÉFONO OCULTO]" in payload


@pytest.mark.parametrize(
    "dato",
    ["12345678-5", "12.345.678-K", "9.876.543-2", "JUAN@CORREO.CL", "+56 9 1234 5678", "912345678"],
)
def test_otros_formatos_tampoco_viajan(cliente, dato):
    engine.clasificar(_entrada(f"Tos seca. Dato: {dato}"))
    assert dato not in cliente.payload()


def test_payload_solo_tiene_campos_del_contrato(cliente):
    engine.clasificar(_entrada(MOTIVO_CON_PII))
    llamada = cliente.ultima()

    # Solo estos argumentos van a la API de Anthropic: nada de metadata ni ids.
    assert set(llamada) == {"model", "max_tokens", "system", "messages"}
    assert len(llamada["messages"]) == 1 and llamada["messages"][0]["role"] == "user"

    payload = cliente.payload().lower()
    for clave in ("patient_id", "paciente_id", "episodio_id", "rut", "nombre", "email",
                  "telefono", "fecha_nacimiento", "direccion", "prevision"):
        assert f'"{clave}"' not in payload, f"la clave {clave} viajó a la IA"


@requiere_db
def test_evaluate_de_punta_a_punta_no_envia_datos_del_paciente(cliente):
    from test_decision_db import SIGNOS as SIGNOS_API
    from test_decision_db import _post, _rut_unico

    rut = _rut_unico()
    nombre = "Ana Soto Contreras"
    correo = "ana.soto@correo.cl"
    telefono = "+56987654321"
    direccion = "Av. Siempre Viva 742, Ñuñoa"

    p = _post(
        "/api/v1/patients",
        json={
            "rut": rut, "name": nombre, "birth_date": "1980-01-01", "biological_sex": "female",
            "address": direccion, "phone": telefono, "email": correo, "has_consent": True,
        },
    )
    assert p.status_code == 201, p.text
    patient_id = p.json()["patient_id"]

    motivo = f"Dolor abdominal. Mi RUT es {rut}, correo {correo}, fono {telefono}. Soy de Fonasa."
    f = _post(
        "/api/v1/triage/formulario",
        json={"patient_id": patient_id, "signos_vitales": SIGNOS_API, "motivo_consulta": motivo},
    )
    assert f.status_code == 201, f.text
    episodio_id = f.json()["episodio_id"]

    admin_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"]

    # 1) Antes de guardar: el motivo queda sanitizado en la base.
    with psycopg.connect(admin_url) as conn:
        (guardado,) = conn.execute(
            "SELECT motivo_consulta_texto_libre FROM episodio_triage WHERE episodio_id = %s",
            (episodio_id,),
        ).fetchone()
    for dato in (rut, correo, telefono):
        assert dato not in guardado, f"'{dato}' quedó guardado en el episodio"

    # 2) Antes de llamar a la IA: el payload real no lleva nada identificable.
    r = _post(f"/api/v1/triage/{episodio_id}/evaluate")
    assert r.status_code == 201, r.text
    payload = cliente.payload()

    cuerpo_rut = rut.split("-")[0].replace(".", "")
    prohibidos = [rut, cuerpo_rut, nombre, "Soto", patient_id, episodio_id, "1980-01-01",
                  correo, telefono, "87654321", "Siempre Viva", "Ñuñoa"]
    for dato in prohibidos:
        assert dato not in payload, f"'{dato}' viajó a la IA"
    assert "fonasa" not in payload.lower()
    assert "Edad:" in payload and "Dolor abdominal" in payload

    # 3) Lo que queda en la auditoría es exactamente lo que se envió.
    with psycopg.connect(admin_url) as conn:
        (prompt_auditado,) = conn.execute(
            "SELECT prompt_enviado FROM registro_auditoria WHERE episodio_id = %s "
            "AND prompt_enviado IS NOT NULL",
            (episodio_id,),
        ).fetchone()
    # S10-5: el registro agrega version del prompt, modelo y respuesta alrededor de la ficha enviada.
    assert "version_prompt: " in prompt_auditado and "modelo: " in prompt_auditado
    ficha_auditada = prompt_auditado.split("--- ficha enviada ---\n", 1)[1].split("\n--- respuesta ---", 1)[0]
    assert ficha_auditada == cliente.ultima()["messages"][0]["content"]