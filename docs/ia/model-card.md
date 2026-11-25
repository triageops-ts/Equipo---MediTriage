# Model card · Motor de sugerencia ESI de MediTriage (S12-15)

**Estado:** versión del 24-11-2026 · **Responsable:** equipo MediTriage (Taller de Ingeniería de Software)
**Documentos relacionados:** `docs/ia/motor-ia.md` (cómo está construido) · `docs/ia/evaluacion.md` (cómo se midió) ·
`docs/data/contrato-ia.md` (datos de entrada y salida) · `docs/data/guardrails-ia.md` · `docs/security/prompt-injection.md`

## 1. Qué es

Un componente que recibe la ficha clínica **anonimizada** de un paciente que llega a urgencias y **sugiere** un nivel ESI
(Emergency Severity Index, de 1 = reanimación inmediata a 5 = no urgente) con una justificación breve en español.
Es una ayuda para la enfermera de triage. **No decide**: la decisión final es siempre de una persona y queda registrada.

## 2. Modelo y versión del prompt

| Dato | Valor |
|---|---|
| Motor | Claude (Anthropic, API externa) con respaldo propio de reglas |
| Modelo por defecto | `claude-haiku-5-5` (variable `ANTHROPIC_MODEL`) |
| Versión del prompt | `esi-v3`, huella `ab595a512ab7` (SHA-256, primeros 12 caracteres) |
| Respaldo | Árbol de reglas determinista (`fallback-rule-engine`), sin red ni IA |
| Límite de tiempo | 1500 ms; si se pasa, responde el respaldo |
| Qué motor se usa hoy | **El respaldo de reglas.** El proyecto no tiene `ANTHROPIC_API_KEY`; el equipo decidió (S12-2) presentar la demo final con el respaldo. Cada respuesta indica `modelo_usado` y `fallback_aplicado`. |

La versión y la huella del prompt quedan en el registro de auditoría de cada inferencia. Una prueba automática
(`tests/test_auditoria_prompt.py`) falla si el prompt cambia sin subir la versión.

**Importante:** todo lo que se midió (ver sección 6) corresponde al respaldo de reglas. Cómo se comporta Claude con
este prompt **no está medido**: falta la clave.

## 3. Uso previsto

- **Para quién:** enfermeras y enfermeros de triage en un servicio de urgencias de atención primaria en Chile.
- **Para qué:** proponer un nivel ESI y explicar en lenguaje natural en qué signos y síntomas se apoya, para acelerar y dar
  trazabilidad a la categorización.
- **Cómo:** la enfermera ve la sugerencia, la confirma o la cambia con una justificación de al menos 10 caracteres, y el
  sistema guarda su decisión final, si coincide con la IA y quién la tomó.
- **Quién ve qué:** la sala de espera pública solo muestra un turno anonimizado y el nivel confirmado por enfermería, nunca
  la sugerencia de la IA ni datos del paciente.

## 4. Fuera de alcance (no usar para)

- Diagnosticar, indicar tratamientos o reemplazar el juicio clínico.
- Decidir un nivel sin que una persona lo revise y lo confirme.
- **Pacientes pediátricos**: los umbrales del respaldo son de adulto y tienden a sobreclasificar en niños.
- Embarazadas, pacientes con condiciones crónicas particulares o situaciones que dependan de la historia clínica: la IA no
  recibe historial.
- Usarlo con datos reales de pacientes mientras el equipo clínico no revise los niveles y umbrales y no haya una revisión legal.
- Priorizar según previsión de salud, nivel socioeconómico o lugar de residencia (están prohibidos como variables).

## 5. Datos de entrada y salida

Detalle completo en `docs/data/contrato-ia.md`. En resumen:

- **Entra** solo lo que está en la lista cerrada: edad en años, sexo biológico, 8 signos vitales, síntomas (código, severidad y
  horas de evolución) y el motivo de consulta (texto libre, sanitizado). El contrato rechaza cualquier campo de más.
- **Nunca entra** (sin PII): RUT, nombre, teléfono, correo, dirección, contacto de emergencia, fecha de nacimiento exacta,
  identificadores de paciente o episodio, previsión de salud, nivel socioeconómico ni ubicación. En el texto libre, el RUT, el
  correo y el teléfono se reemplazan antes de armar el prompt, y se filtran los intentos de manipular al modelo.
- **Sale** un JSON con `nivel_esi` (entero de 1 a 5) y `justificacion` (10 a 600 caracteres). Si algo no cumple el formato o
  rompe un guardrail (G1 a G5), se descarta y responde el respaldo.
- **Entrenamiento:** el equipo no entrenó ni ajustó ningún modelo. Se usa el modelo del proveedor tal como viene, con un prompt
  fijo; el respaldo es un conjunto de reglas escrito a mano con umbrales fisiológicos de adulto.

## 6. Evaluación

Golden set de **15 casos sintéticos** (`docs/ia/golden-set.json`): los 10 casos límite de la batería de guardrails y los 5
pacientes de demo, uno por nivel ESI. Resultado con el respaldo de reglas (detalle en `docs/ia/evaluacion.md`):

| Medida | Resultado |
|---|---|
| Acierto exacto | 12 de 15 (80,0 %) |
| Acierto a ±1 nivel | 15 de 15 (100 %) |
| Subclasificación (menos urgente que lo esperado) | 0 de 15 |
| Sobreclasificación (más urgente que lo esperado) | 3 de 15 |

Es una evaluación **pequeña, hecha por el mismo equipo** y los niveles esperados **no los ha validado personal clínico**.
Sirve para detectar regresiones y para mostrar un método, no como validación clínica.

## 7. Limitaciones y riesgos

| Riesgo | Qué se hizo | Qué falta |
|---|---|---|
| Subclasificar a un paciente grave | Guardrails G3 y G4 (con signo crítico, nunca ESI 4 o 5); el respaldo peca de prudente; decide la enfermera | G3 acepta ESI 3 con signos críticos; sin signos críticos ningún guardrail bloquea un ESI 4 o 5 de Claude |
| Sobreclasificar (saturar la urgencia) | Se mide en el golden set (3 de 15) | Revisar umbrales con el equipo clínico |
| Niños | Documentado como fuera de alcance | Umbrales pediátricos |
| Texto libre malicioso (prompt injection) | Filtro de 4 categorías, texto marcado como dato, guardrails | El filtro es de patrones: no cubre paráfrasis ni otros idiomas |
| Sesgo por previsión, nivel socioeconómico o ubicación | Variables prohibidas en 3 capas (contrato, texto libre, guardrail G5) | Lista de palabras aproximada |
| Dependencia de un proveedor externo | Respaldo local; solo salen datos clínicos anonimizados | Sin clave no hay medición con Claude |
| Exceso de confianza en la sugerencia | La IA solo sugiere; para cambiar el nivel hace falta justificar; todo queda auditado | Capacitación del personal |
| Códigos de síntoma de texto libre | — | Validarlos contra un catálogo |

## 8. Supervisión humana y trazabilidad

- La enfermera siempre ve la sugerencia y decide. Se guarda `nivel_esi_final`, si coincide con la IA y la justificación del cambio.
- Cada inferencia deja un registro de auditoría inmutable (cadena de hashes SHA-256) con el modelo, la versión y la huella del
  prompt, la latencia y si respondió el respaldo, sin datos personales (`docs/data/auditoria-inmutable.md`).
- El rol auditor puede consultar y verificar ese registro.

## 9. Marco legal

El sistema trata datos de salud, que la ley chilena considera datos sensibles. Marco que el equipo ha tomado como referencia
(ver también `docs/CHARTER.md` y el ADR IA-001):

- **Ley 19.628** sobre protección de la vida privada: vigente. Regula el tratamiento de datos personales y trata los datos
  relativos a la salud como sensibles.
- **Ley 21.719**, que regula la protección y el tratamiento de los datos personales y modifica la Ley 19.628. Su fecha legal de
  entrada en vigencia es el **1 de diciembre de 2026**. El **17 de noviembre de 2026** la Cámara de Diputados despachó un
  proyecto que la posterga hasta el **15 de octubre de 2027**; a la fecha de este documento falta su promulgación y publicación,
  y solo tiene efecto una vez publicado. El equipo debe volver a revisar la fecha vigente antes de la presentación.
- **Cómo lo refleja el diseño:** minimización (la IA recibe solo datos clínicos anonimizados y la edad, no la fecha de
  nacimiento), cifrado de columnas sensibles y control por filas en la base, auditoría inmutable, y decisión final humana
  (el ADR IA-001 recoge que las decisiones automatizadas deben poder ser revisadas por una persona).
- **Límite de este apartado:** es una lectura del equipo de estudiantes, **no asesoría jurídica**. Para un uso real habría que hacer
  una revisión legal (base de licitud, consentimiento, transferencia a un proveedor en el extranjero, derechos de las personas).

Fuentes consultadas el 24-11-2026: [Garrigues, «Chile redefine el marco de privacidad y ciberseguridad»](https://www.garrigues.com/es_ES/noticia/chile-redefine-marco-privacidad-ciberseguridad-nuevas-reglas-cumplimiento-cambios.md) ·
[Bezal, «El Congreso despachó la postergación de la Ley 21.719»](https://www.bezal.cl/blog/congreso-despacha-postergacion-ley-21719).

## 10. Mantenimiento

Si cambia el modelo, el prompt, los umbrales del respaldo o el contrato de datos, hay que actualizar esta ficha, `motor-ia.md`
y repetir la evaluación (`python scripts/evaluar_golden_set.py`) en el mismo PR. Cuando exista una clave de Claude, repetirla
con `--corridas 3` y anotar el resultado en `docs/ia/evaluacion.md`.
