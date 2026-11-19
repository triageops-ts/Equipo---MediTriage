# Contrato de datos clínico → IA (Tarjeta S09-4)

**Versión:** 1.0 · **Código:** `backend/app/ai/contrato.py` (el contrato se hace cumplir ahí, no solo aquí)
**Motor:** `backend/app/ai/engine.py` · **Respaldo:** `backend/app/ai/reglas.py` · **Decisión del motor:** ADR IA-001

## Qué es

Es la lista exacta de datos que la IA puede recibir y de lo que debe devolver. Todo lo que no
esté en la lista de campos permitidos **no viaja** a la IA: el modelo `EntradaIA` rechaza con un
error cualquier campo de más (`extra="forbid"`), en vez de enviarlo sin que nadie lo note.
La clasificación de cada dato como personal o clínico está en `docs/data/clasificacion_pii.md`.

## Entrada: campos permitidos

| Campo | Tipo y rango | Observación |
|---|---|---|
| `edad_anios` | entero, 0 a 120 | Años cumplidos. **No** la fecha de nacimiento. |
| `sexo_biologico` | `masculino`, `femenino` o vacío | Dato clínico. |
| `signos_vitales.presion_sistolica` | entero, 40 a 260 mmHg | Mismos rangos del formulario clínico (`schemas/triage.py`). |
| `signos_vitales.presion_diastolica` | entero, 20 a 200 mmHg | Debe ser menor que la sistólica. |
| `signos_vitales.frecuencia_cardiaca` | entero, 20 a 300 lpm | |
| `signos_vitales.frecuencia_respiratoria` | entero, 5 a 80 rpm | |
| `signos_vitales.temperatura` | decimal, 30,0 a 43,0 °C | |
| `signos_vitales.saturacion_oxigeno` | entero, 0 a 100 % | |
| `signos_vitales.escala_dolor` | entero, 0 a 10 | |
| `signos_vitales.nivel_conciencia` | `alerta`, `verbal`, `dolor`, `inconsciente` | |
| `sintomas[]` | hasta 30 | Cada uno: `codigo_sintoma`, `severidad` (`leve`, `moderada`, `severa`) y `tiempo_evolucion_horas` (opcional). |
| `motivo_consulta` | texto, hasta 1000 caracteres, opcional | Se **sanitiza otra vez** dentro del contrato: RUT, correo y teléfono se reemplazan por `[RUT OCULTO]`, `[EMAIL OCULTO]` y `[TELÉFONO OCULTO]`. |

## Entrada: campos prohibidos (nunca llegan a la IA)

| Campo | Por qué |
|---|---|
| RUT | PII directa. |
| Nombre completo | PII directa. |
| Teléfono, correo, dirección | PII directa (contacto). |
| Contacto de emergencia | PII directa de un tercero. |
| Previsión de salud | Dato personal que no aporta a la clasificación. |
| Fecha de nacimiento exacta | Cuasi-identificador: se envía solo la edad. |
| `patient_id`, `episodio_id`, `usuario_id` | La IA no necesita ids; la correlación usa el token efímero, que no forma parte del prompt. |
| Firma digital, consentimientos | Datos legales, no clínicos. |
| Historial de otros pacientes | Cada inferencia es independiente (Factor 06). |

## Salida

El modelo debe responder **solo un JSON** con estos dos campos. Se valida con Pydantic (`SalidaIA`)
antes de usarse; si falta algo o está fuera de rango, se aplica el respaldo.

| Campo | Regla |
|---|---|
| `nivel_esi` | entero de 1 a 5 |
| `justificacion` | texto en español, de 10 a 600 caracteres, en lenguaje natural |

Lo que recibe el resto del backend (`ClasificacionIA`, igual venga de Claude o del respaldo):

| Campo | Significado |
|---|---|
| `nivel_esi_sugerido` | 1 a 5 |
| `justificacion` | texto para la enfermera |
| `modelo_usado` | nombre del modelo, o `fallback-rule-engine` si respondió el respaldo |
| `latencia_ms` | tiempo total de la clasificación |
| `fallback_aplicado` | `true` si se usó el árbol de reglas |

Estos nombres coinciden con la tabla `clasificacion_ia` y con los eventos `ia.clasificacion.sugerida` y
`triage.clasificacion.respaldo_aplicada` del catálogo de eventos.

## Ejemplo

Entrada:

```json
{
  "edad_anios": 54,
  "sexo_biologico": "masculino",
  "signos_vitales": {
    "presion_sistolica": 140,
    "presion_diastolica": 90,
    "frecuencia_cardiaca": 110,
    "frecuencia_respiratoria": 22,
    "temperatura": 37.2,
    "saturacion_oxigeno": 94,
    "escala_dolor": 6,
    "nivel_conciencia": "alerta"
  },
  "sintomas": [
    {"codigo_sintoma": "dolor_toracico", "severidad": "moderada", "tiempo_evolucion_horas": 2},
    {"codigo_sintoma": "disnea", "severidad": "leve", "tiempo_evolucion_horas": 2}
  ],
  "motivo_consulta": "Dolor en el pecho desde hace dos horas"
}
```

Salida de la IA:

```json
{
  "nivel_esi": 2,
  "justificacion": "Dolor torácico con taquicardia y saturación en el límite bajo sugieren riesgo cardiovascular que no debe esperar."
}
```

Resultado para el backend:

```json
{
  "nivel_esi_sugerido": 2,
  "justificacion": "Dolor torácico con taquicardia y saturación en el límite bajo sugieren riesgo cardiovascular que no debe esperar.",
  "modelo_usado": "claude-haiku-5-5",
  "latencia_ms": 1180,
  "fallback_aplicado": false
}
```

## Qué pasa si la IA falla

El límite es de **1500 ms** en total (ADR 0004). Si Claude no responde a tiempo, hay un error de red
o de cuota, falta la clave o la respuesta no cumple el formato de salida, se usa el árbol de reglas
y el resultado sale con `fallback_aplicado = true` y `modelo_usado = "fallback-rule-engine"`.
La enfermera siempre recibe una sugerencia; el motor nunca lanza un error por culpa de la IA.
Desde la S09-10 el respaldo también se usa si la respuesta de la IA rompe un guardrail (nivel fuera de 1 a 5,
justificación vacía o incoherente, signo crítico con ESI 4 o 5, uso de previsión o ubicación). Ver `docs/data/guardrails-ia.md`.

## Reglas del motor

- **Sin memoria (Factor 06):** cada llamada arma su prompt solo con la entrada recibida. No hay
  historial de conversación ni de pacientes en memoria.
- **Clave solo por entorno:** `ANTHROPIC_API_KEY`, sin valor por defecto (ver `.env.example`). El modelo
  se cambia con `ANTHROPIC_MODEL`.
- **Logs sin datos del paciente:** solo el tipo de error y la latencia.
- **La decisión final es de la enfermera:** la IA solo sugiere.

## Pendiente

- Los umbrales del árbol de reglas son una aproximación con valores de adulto. Debe revisarlos el
  equipo clínico; para niños tenderá a sobreclasificar.
- ~~Falta el paso que arma `EntradaIA` desde la base de datos~~ Resuelto en S09-7: `POST /api/v1/triage/{episodio_id}/evaluate`
  lee el episodio, calcula la edad desde la fecha de nacimiento (que no viaja), toma los últimos signos y los síntomas,
  llama a `clasificar` y guarda el resultado en `clasificacion_ia` (migración 0009: `fallback_aplicado` e `idempotency_key`).
- El `motivo_consulta` sigue viajando a la IA (el contrato lo permite) y solo se sanitiza RUT, correo y teléfono: un nombre
  escrito a mano en el texto libre no se detecta. Decidir con el equipo si se excluye mientras ese campo no se cifre.
  Desde la S09-10, las menciones de previsión (Fonasa/Isapre), nivel socioeconómico y ubicación dentro de ese texto se
  reemplazan por `[OMITIDO]` antes de armar el prompt; los nombres siguen sin detectarse.
