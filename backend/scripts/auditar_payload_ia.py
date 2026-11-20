"""S09-8: muestra el payload REAL que saldría hacia Claude en 10 casos de prueba.

Uso, desde la carpeta backend (no necesita base de datos, clave de IA ni internet):

    python scripts/auditar_payload_ia.py

Reemplaza solo el cliente de Anthropic por uno falso que guarda lo que recibiría
`messages.create`; el resto (contrato, sanitizador, guardrails, ficha) es el código real.
Para cada caso imprime el motivo original y el mensaje exacto que viajaría. La revisión es
MANUAL: anotar el resultado de cada caso en docs/data/auditoria-payload-ia.md.
"""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.ai import engine  # noqa: E402
from app.ai.contrato import EntradaIA  # noqa: E402

SIGNOS = dict(
    presion_sistolica=125,
    presion_diastolica=82,
    frecuencia_cardiaca=88,
    frecuencia_respiratoria=18,
    temperatura=37.2,
    saturacion_oxigeno=97,
    escala_dolor=5,
    nivel_conciencia="alerta",
)

# Cada caso prueba un tipo de dato identificable distinto (datos ficticios).
CASOS = [
    ("RUT con puntos y guion", "Dolor torácico opresivo desde anoche. Mi RUT es 15.234.567-8."),
    ("RUT sin puntos ni guion", "Fiebre alta hace 2 días. Mi rut es 152345678"),
    ("Correo electrónico", "Tos seca hace 3 días. Si necesitan algo escriban a maria.lopez@gmail.com"),
    ("Correo escrito en palabras", "Dolor de garganta. Mi correo es maria punto lopez arroba gmail punto com"),
    ("Celular con espacios", "Vómitos desde la mañana. Llamar a mi hijo al +56 9 8765 4321"),
    ("Teléfono fijo", "Mareos al levantarse. Teléfono de mi casa 22 345 6789"),
    ("Nombres propios", "Me trajo mi hija Camila Rojas. Soy Pedro González, tengo dolor abdominal"),
    ("Dirección", "Caída en la escalera de mi casa en Av. Providencia 1234 depto 56, dolor en tobillo"),
    ("Previsión y comuna", "Dolor lumbar intenso. Soy de Fonasa tramo B y vivo en La Florida"),
    ("Fecha de nacimiento + RUT + celular", "Cefalea fuerte. Nací el 03/05/1980, RUT 9.876.543-K, cel 987654321"),
]


class ClienteFalso:
    def __init__(self):
        self.ultima = None
        self.messages = self

    def create(self, **kwargs):
        self.ultima = kwargs
        texto = json.dumps({"nivel_esi": 3, "justificacion": "Respuesta falsa para la auditoría del payload."})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)])


def main() -> None:
    falso = ClienteFalso()
    engine._cliente_anthropic = lambda api_key, timeout_s: falso
    os.environ["ANTHROPIC_API_KEY"] = "clave-falsa-de-auditoria"

    for n, (tipo, motivo) in enumerate(CASOS, 1):
        entrada = EntradaIA(
            edad_anios=45, sexo_biologico="masculino", signos_vitales=SIGNOS, motivo_consulta=motivo
        )
        engine.clasificar(entrada)
        llamada = falso.ultima
        if n == 1:
            print("=" * 80)
            print("Argumentos enviados a messages.create:", sorted(llamada))
            print("Modelo:", llamada["model"])
            print("(El prompt de sistema es fijo y no contiene datos del paciente.)")
        print("=" * 80)
        print(f"CASO {n}: {tipo}")
        print(f"Motivo original: {motivo}")
        print("-" * 80)
        print(llamada["messages"][0]["content"])
    print("=" * 80)


if __name__ == "__main__":
    main()