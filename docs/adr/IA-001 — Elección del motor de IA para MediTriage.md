# ADR IA - 001 — Elección del motor de IA para MediTriage

## Fecha

24/08/2026

## Autores

Lucas Benítez, Kimberlly Guillén, Josefa Rodríguez, Marcela Contreras, Isidora Ramos y Antonia Moya

## Contexto

El sistema MediTriage necesita un motor de inteligencia artificial que analice síntomas y signos vitales de los pacientes y sugiera un nivel de urgencia según el ESI (Emergency Severity Index). Además, debe generar una justificación clínica clara y explicable, porque la normativa chilena (Ley 21.719) exige que las decisiones automatizadas puedan ser revisadas por humanos.

### El motor debe cumplir los siguientes criterios

- Latencia < 3 segundos.
- Salida estructurada en formato JSON.
- Integración sencilla con Python (FastAPI + LangChain).
- Costo razonable por volumen de consultas.
- Cumplimiento de normas de privacidad y anonimización de datos sensibles.

### Se evaluaron tres opciones principales

- OpenAI (ChatGPT): alta precisión y comunidad amplia, pero con costos mayores y latencia superior en GPT‑4.
- Google Gemini 1.5 Pro: buena integración con Google Cloud, pero configuración más compleja y menor soporte para salidas JSON.
- Claude 3 Haiku (Anthropic): rápido, de menor costo y con SDK oficial en Python y compatibilidad con LangChain (opción elegida).

## Decisión y razones

Se elige Claude 3 Haiku como motor de IA principal para MediTriage porque ofrece el mejor equilibrio entre velocidad, costo y calidad de salida.

Claude 3 Haiku responde en ≈ 1–2 segundos, lo que cumple el requisito de latencia crítica en urgencias. Su costo es más bajo que GPT‑4 y Gemini, lo que permite escalar sin comprometer presupuesto. Además, cuenta con un SDK oficial en Python y compatibilidad con LangChain, lo que facilita la integración con el backend y la generación de salidas JSON estructuradas.

En términos de explicabilidad clínica, Claude produce respuestas claras y comprensibles, adecuadas para justificar la clasificación ESI ante médicos y enfermeras.

En resumen, Claude 3 Haiku es rápido, económico, fácil de integrar y genera explicaciones confiables, lo que lo convierte en la mejor opción para MediTriage.

## Alternativas descartadas

- **OpenAI (GPT-4):** descartado por mayor costo y mayor latencia, que ponen en riesgo el límite de respuesta de urgencias.
- **Google Gemini 1.5 Pro:** descartado por configuración más compleja y menor soporte para salidas JSON estructuradas, que el contrato de datos exige.
- **Modelo abierto propio (por ejemplo LLaMA o Mistral alojado por el equipo):** descartado porque obliga a operar y dimensionar infraestructura de inferencia que el equipo no tiene, y sin ajuste clínico no hay garantía de que explique mejor la clasificación. Queda como opción futura si se quiere que los datos no salgan a un proveedor externo (ver `docs/data/bounded_contexts.md`).
- **Solo reglas (árbol de decisión determinista, sin modelo de lenguaje):** descartado como motor principal porque no interpreta el texto libre de los síntomas ni redacta una justificación clara para el personal clínico. Sí se usa como respaldo: si la IA falla o tarda demasiado, el árbol de reglas entrega igual una sugerencia.

## Razón de la elección frente a las alternativas

Claude Haiku es el único que cumple a la vez los cinco criterios: latencia baja, salida JSON, integración simple con Python y LangChain, costo razonable y datos anonimizados. Combinado con el árbol de reglas como respaldo, cubre tanto la calidad de la explicación como la disponibilidad cuando el proveedor falla.

## Actualización (22/11/2026, tarjeta S11-5)

Lo construido difiere del texto de arriba en estos puntos. La decisión de fondo (Anthropic con un modelo
Haiku, integrado por LangChain) se mantiene; la descripción actual del motor está en `docs/ia/motor-ia.md`.

- **Modelo en uso:** `claude-haiku-5-5` (Claude Haiku 5.5), configurable con la variable `ANTHROPIC_MODEL`.
  Reemplaza a Claude 3 Haiku, que es el que nombra la decisión original.
- **Latencia:** el límite operativo es de 1500 ms (ADR 0004), más estricto que los 3 s de los criterios de este ADR.
  Si se supera, se usa el árbol de reglas de respaldo.
- **Protecciones agregadas después del ADR:** árbol de reglas de respaldo, guardrails de salida (S09-10) y
  filtro anti prompt-injection (S10-8).
- **Pendiente:** el tiempo de respuesta de 1 a 2 s del ADR se estimó para Claude 3 Haiku. Con `claude-haiku-5-5` y
  la clave real aún no se ha medido (ver `docs/ia/motor-ia.md`, sección 8).
