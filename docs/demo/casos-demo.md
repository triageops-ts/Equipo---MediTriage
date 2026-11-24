# Casos de demostración (S12-8)

Cinco casos **ficticios**, uno por nivel ESI, para digitar en vivo en la presentación final. Los nombres, fechas de nacimiento y motivos están inventados. Los RUT tienen dígito verificador válido, pero usan cuerpos entre 90.000.001 y 90.000.005, el rango que en Chile se asigna a personas jurídicas, por lo que no corresponden a ninguna persona.

**Motor que se usa:** respaldo de reglas (`fallback-rule-engine`), decisión del equipo en S12-2 porque no hay clave de Claude. Es determinista: los mismos datos dan siempre el mismo nivel. La columna "ESI obtenido" se midió con ese motor. Si algún día se conecta Claude real, el nivel podría variar y habría que volver a probar los 5 casos.

> Las edades y los umbrales del respaldo son aproximaciones de adulto y no reemplazan el juicio clínico (ver `docs/ia/motor-ia.md`).

## Resumen

| # | Paciente | RUT | ESI esperado | ESI obtenido |
|---|---|---|---|---|
| 1 | Marcela Fuentes Oyarzún | 90.000.001-4 | 1 | 1 |
| 2 | Rodrigo Palma Soto | 90.000.002-2 | 2 | 2 |
| 3 | Camila Vergara Núñez | 90.000.003-0 | 3 | 3 |
| 4 | Tomás Araya Leiva | 90.000.004-9 | 4 | 4 |
| 5 | Isabel Montero Rivas | 90.000.005-7 | 5 | 5 |

## Cómo digitarlos en la pantalla del enfermero

1. Iniciar sesión como `enfermero@meditriage.test`.
2. Escribir el RUT; como el paciente es nuevo, completar nombre, fecha de nacimiento y sexo, y marcar el consentimiento.
3. En anamnesis, escribir el motivo de consulta; poner la escala de dolor.
4. Completar los signos vitales de la tabla del caso.
5. Agregar los síntomas (código, severidad y evolución en horas). El caso 5 no lleva síntomas.
6. Guardar y pedir la evaluación de la IA. Comparar el nivel que aparece con el "ESI esperado".

La sala de espera pública solo muestra un turno anonimizado una vez que la enfermera confirma el nivel.

## Caso 1 · ESI 1 — atención inmediata

- **Paciente:** Marcela Fuentes Oyarzún · RUT 90.000.001-4 · nacida el 14-03-1962 · femenino
- **Motivo:** Dificultad respiratoria intensa y mareo.
- **Signos vitales:** presión 76/44 mmHg · pulso 142 lpm · frecuencia respiratoria 34/min · temperatura 36,2 °C · saturación 84 % · dolor 6/10 · conciencia: alerta
- **Síntomas:** DISNEA, severa, 1 h
- **ESI esperado:** 1 · **ESI obtenido:** 1
- **Justificación del respaldo:** saturación de oxígeno 84 %; presión sistólica 76 mmHg.

## Caso 2 · ESI 2 — alto riesgo

- **Paciente:** Rodrigo Palma Soto · RUT 90.000.002-2 · nacido el 02-09-1971 · masculino
- **Motivo:** Dolor opresivo en el pecho desde hace una hora.
- **Signos vitales:** presión 150/95 mmHg · pulso 112 lpm · frecuencia respiratoria 20/min · temperatura 36,8 °C · saturación 92 % · dolor 8/10 · conciencia: alerta
- **Síntomas:** DOLOR_TORACICO, severa, 1 h
- **ESI esperado:** 2 · **ESI obtenido:** 2
- **Justificación del respaldo:** saturación de oxígeno 92 %; dolor 8/10; síntoma de severidad severa.

## Caso 3 · ESI 3 — urgente, estable

- **Paciente:** Camila Vergara Núñez · RUT 90.000.003-0 · nacida el 23-11-1994 · femenino
- **Motivo:** Fiebre y tos de dos días.
- **Signos vitales:** presión 118/76 mmHg · pulso 108 lpm · frecuencia respiratoria 22/min · temperatura 38,4 °C · saturación 97 % · dolor 5/10 · conciencia: alerta
- **Síntomas:** FIEBRE, moderada, 48 h · TOS, moderada, 48 h
- **ESI esperado:** 3 · **ESI obtenido:** 3
- **Justificación del respaldo:** frecuencia cardíaca 108 lpm; frecuencia respiratoria 22/min; temperatura 38,4 °C; dolor 5/10; 2 síntomas simultáneos.

## Caso 4 · ESI 4 — menos urgente

- **Paciente:** Tomás Araya Leiva · RUT 90.000.004-9 · nacido el 30-05-2001 · masculino
- **Motivo:** Dolor de garganta leve desde ayer.
- **Signos vitales:** presión 122/80 mmHg · pulso 76 lpm · frecuencia respiratoria 16/min · temperatura 36,7 °C · saturación 98 % · dolor 2/10 · conciencia: alerta
- **Síntomas:** DOLOR_GARGANTA, leve, 24 h
- **ESI esperado:** 4 · **ESI obtenido:** 4
- **Justificación del respaldo:** un síntoma aislado; dolor 2/10.

## Caso 5 · ESI 5 — no urgente

- **Paciente:** Isabel Montero Rivas · RUT 90.000.005-7 · nacida el 17-01-1988 · femenino
- **Motivo:** Control y renovación de receta, sin molestias.
- **Signos vitales:** presión 116/74 mmHg · pulso 72 lpm · frecuencia respiratoria 15/min · temperatura 36,5 °C · saturación 99 % · dolor 0/10 · conciencia: alerta
- **Síntomas:** ninguno
- **ESI esperado:** 5 · **ESI obtenido:** 5
- **Justificación del respaldo:** signos vitales normales y sin síntomas registrados.

## Notas para quien presente

- Cada paciente se registra una sola vez. Si se repite la demo sobre la misma base, el RUT ya existe: se busca por RUT y se crea un episodio nuevo. Para empezar de cero: `docker compose down -v` y repetir los pasos de levantado.
- El motivo de consulta no cambia el nivel que calcula el respaldo; lo definen los signos vitales y los síntomas. Sirve para contar el caso.
- Los 5 casos se probaron con el motor de respaldo: nivel obtenido igual al esperado y latencia del motor de 0 ms.
