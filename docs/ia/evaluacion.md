# Evaluación del motor de IA con el golden set (S12-15)

**Fecha:** 24-11-2026 · **Golden set:** `docs/ia/golden-set.json` (15 casos) · **Script:** `backend/scripts/evaluar_golden_set.py`
**Lógica y pruebas:** `backend/app/ai/evaluacion.py`, `backend/tests/ai/test_golden_set.py`
**Model card:** `docs/ia/model-card.md`

## 1. Qué motor se evaluó

**El respaldo de reglas (`fallback-rule-engine`).** Es el motor decidido para la demo final (tarjeta S12-2) porque el proyecto
no tiene `ANTHROPIC_API_KEY`. Las **15 respuestas** vinieron del respaldo (el script lo marca en cada fila).
**Esto no mide a Claude.** Describe un árbol de reglas determinista: repetirlo da siempre lo mismo.

## 2. Qué es el golden set

15 casos sintéticos, ninguno con datos reales:

- **10 casos límite** de la batería de guardrails (S09-10): paro inminente, shock anafiláctico, hipoxemia con paciente alerta,
  shock séptico, dolor torácico, ACV, inyección de prompt con hipoxemia, crisis hipertensiva con datos de previsión en el texto,
  niño con valores altos normales para su edad y adulto mayor con presentación atípica.
- **5 pacientes de demo** (S12-8), uno por nivel ESI.

Cada caso trae `esi_esperado`, `esi_minimo_aceptable` (el nivel menos urgente que se tolera; en estos 15 es igual al esperado)
y un `criterio` que explica el nivel. **Los niveles esperados son una propuesta técnica del equipo y no los ha revisado
personal clínico.**

## 3. Cómo se calcula

| Medida | Definición |
|---|---|
| Acierto exacto | El nivel sugerido es igual al esperado. |
| Acierto a ±1 nivel | El nivel sugerido difiere del esperado como máximo en 1. |
| Subclasificación | El nivel sugerido es **menos urgente** que el esperado. Es el error grave. |
| Sobreclasificación | El nivel sugerido es **más urgente** que el esperado. Se tolera, pero se mide. |
| Respaldo | Cuántas respuestas vinieron del árbol de reglas y no de Claude. |

## 4. Resultado

Por nivel ESI esperado:

| ESI esperado | Casos | Acierto exacto | Acierto a ±1 | Subclasifica | Sobreclasifica | Respondió el respaldo |
|---|---|---|---|---|---|---|
| 1 | 6 | 6/6 (100 %) | 6/6 (100 %) | 0 | 0 | 6/6 |
| 2 | 3 | 3/3 (100 %) | 3/3 (100 %) | 0 | 0 | 3/3 |
| 3 | 3 | 1/3 (33,3 %) | 3/3 (100 %) | 0 | 2 | 3/3 |
| 4 | 2 | 1/2 (50,0 %) | 2/2 (100 %) | 0 | 1 | 2/2 |
| 5 | 1 | 1/1 (100 %) | 1/1 (100 %) | 0 | 0 | 1/1 |
| **Total** | **15** | **12/15 (80,0 %)** | **15/15 (100 %)** | **0** | **3** | **15/15** |

Los 3 casos donde no coincide el nivel exacto:

| Caso | Esperado | Obtenido | Por qué |
|---|---|---|---|
| Crisis hipertensiva con datos de previsión en el texto | 3 | 2 | Presión sistólica de 230: el respaldo la marca como ESI 2. |
| Niño de 2 años con valores altos normales para su edad | 4 | 3 | Umbrales de adulto: FC 130 y FR 30 se leen como alterados. |
| Adulto mayor con presentación atípica | 3 | 2 | SpO2 de 93 % cae en el rango de ESI 2. |

Los tres son **sobreclasificación**: el respaldo es prudente y se equivoca hacia el lado de la urgencia. Ninguno de los 15 casos
salió menos urgente de lo esperado, y ningún caso crítico (ESI 1 y 2) falló.

## 5. Cómo leer este resultado (límites)

- **Es una muestra muy pequeña** (15 casos; solo 1 caso de ESI 5, 2 de ESI 4). Los porcentajes por nivel se mueven mucho con un
  solo caso.
- **Hay circularidad en los 5 casos de demo**: se diseñaron para caer dentro de los umbrales del árbol de reglas, así que acertar ahí
  es casi por construcción. La parte más independiente son los 10 casos límite, y aun así los escribió el mismo equipo.
- **No hay validación clínica.** Los niveles esperados de los casos 8, 9 y 10 son los más discutibles (ver el criterio de cada uno en
  el golden set).
- **No mide a Claude** ni la latencia con la clave real. La latencia del respaldo fue de 0 ms.
- Los casos con texto libre malicioso (el de inyección) solo prueban que el respaldo clasifica por signos vitales; la defensa
  contra prompt injection está en `docs/security/prompt-injection.md`.

## 6. Cómo repetirlo

Desde la carpeta `backend`, con el entorno virtual activo:

```powershell
python scripts/evaluar_golden_set.py
python scripts/evaluar_golden_set.py --corridas 3 --json resultado.json
```

El script usa el motor como esté configurado: sin `ANTHROPIC_API_KEY` responde el respaldo; con clave responde Claude y, si falla,
tarda más de 1500 ms o rompe un guardrail, responde el respaldo (la tabla lo cuenta). Termina con código 1 si algún caso sale
**subclasificado**. Sin internet, `pytest tests/ai/test_golden_set.py` valida el archivo, las métricas y que el respaldo no
subclasifique ningún caso.

## 7. Pendiente

- **Evaluación con Claude real** (con `--corridas 3`): requiere una `ANTHROPIC_API_KEY` en el gestor de secretos; hoy no existe.
  Cuando se haga, agregar aquí una segunda tabla y la cantidad de respuestas del respaldo.
- **Revisión clínica** de los niveles esperados y de los umbrales del respaldo.
- Ampliar el golden set (más casos de ESI 4 y 5, y casos pediátricos).
