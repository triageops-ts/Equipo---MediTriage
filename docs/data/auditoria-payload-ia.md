# Auditoría del payload enviado a la IA (S09-8)

**Objetivo:** comprobar, con el payload real y no solo leyendo el código, que lo que sale hacia
el proveedor de IA (Claude) no contiene datos identificables del paciente (DoD #3).

- **Fecha de revisión:** 2026-11-19
- **Revisado por:** _(nombre)_
- **Versión revisada:** rama `isi-patch2` sobre `main` (`9aa9949`)

## Cómo se obtuvo el payload

Se usó `backend/scripts/auditar_payload_ia.py`. El script reemplaza solo el cliente de
Anthropic por uno falso que guarda los argumentos exactos de `messages.create`. Todo lo demás es
el código real: el contrato `EntradaIA`, `sanitize_symptoms_text`, los guardrails
(`redactar_variables_prohibidas`) y la construcción de la ficha. No se llamó a internet.

```bash
cd backend
python scripts/auditar_payload_ia.py
```

## Qué viaja al proveedor

- **Argumentos de `messages.create`:** solo `model`, `max_tokens`, `system` y `messages`. No se
  envía metadata, ni ids de usuario, ni ids de paciente o de episodio.
- **`system`:** el prompt fijo del motor. No contiene datos del paciente.
- **`messages`:** un solo mensaje `user` con la ficha. Lleva edad en años, sexo biológico,
  signos vitales, síntomas codificados y el motivo de consulta sanitizado.
- **Nunca viajan** `patient_id`, nombre, RUT, contactos (dirección, teléfono, correo),
  fecha de nacimiento exacta ni previsión como campos. `EntradaIA` usa `extra="forbid"` y la
  ficha solo lee campos del contrato.

**Conclusión:** los campos estructurados están protegidos por diseño. El único lugar por donde
puede filtrarse un dato identificable es el **texto libre del motivo de consulta**, y ese es el
foco de la revisión.

## Revisión manual de 10 payloads

Signos vitales iguales en los 10 casos. Todos los datos son ficticios.

| # | Tipo de dato | Motivo original | Motivo en el payload | Resultado |
|---|---|---|---|---|
| 1 | RUT con puntos y guion | `... Mi RUT es 15.234.567-8.` | `... Mi RUT es [RUT OCULTO].` | ✅ Enmascarado |
| 2 | RUT sin puntos ni guion | `... Mi rut es 152345678` | `... Mi rut es 152345678` | ❌ **Se filtra** |
| 3 | Correo electrónico | `... escriban a maria.lopez@gmail.com` | `... escriban a [EMAIL OCULTO]` | ✅ Enmascarado |
| 4 | Correo escrito en palabras | `... maria punto lopez arroba gmail punto com` | igual al original | ❌ **Se filtra** |
| 5 | Celular con espacios | `... al +56 9 8765 4321` | `... al [TELÉFONO OCULTO]` | ✅ Enmascarado |
| 6 | Teléfono fijo | `... Teléfono de mi casa 22 345 6789` | igual al original | ❌ **Se filtra** |
| 7 | Nombres propios | `Me trajo mi hija Camila Rojas. Soy Pedro González, ...` | igual al original | ❌ **Se filtra** |
| 8 | Dirección | `... en Av. Providencia 1234 depto 56, ...` | igual al original | ❌ **Se filtra** |
| 9 | Previsión y comuna | `... Soy de Fonasa tramo B y vivo en La Florida` | `... Soy de [OMITIDO] [OMITIDO] y [OMITIDO]` | ✅ Omitido (guardrails) |
| 10 | Fecha de nacimiento + RUT + celular | `... Nací el 03/05/1980, RUT 9.876.543-K, cel 987654321` | `... Nací el 03/05/1980, RUT [RUT OCULTO], cel [TELÉFONO OCULTO]` | ⚠️ Parcial: **se filtra la fecha** |

**Resumen:** 4 casos quedan bien (1, 3, 5 y 9). Uno queda parcial (10) y en 5 se filtra el dato
(2, 4, 6, 7 y 8). El sanitizador cumple lo que promete (RUT con guion, correo y celular), pero
el texto libre todavía puede llevar datos identificables hacia la IA.

Las mismas brechas afectan lo que se guarda en `episodio_triage.motivo_consulta_texto_libre` y
en `registro_auditoria.prompt_enviado`, porque ambos usan el mismo sanitizador.

## Patrones que el sanitizador todavía no cubre

| Patrón | Ejemplo | Por qué no se detecta | Posible mitigación |
|---|---|---|---|
| RUT sin guion o con espacios | `152345678`, `15 234 567-8`, `15.234.567 8` | La expresión exige el guion y solo acepta puntos como separador | Aceptar espacio o nada antes del DV y validar con módulo 11 (`app/core/rut.py`) para no enmascarar cualquier número |
| Correo escrito en palabras | `maria punto lopez arroba gmail punto com` | Solo se busca el formato con `@` | Detectar `arroba` junto a un dominio conocido (`gmail`, `hotmail`, `outlook`...) |
| Teléfono fijo | `22 345 6789`, `+56 2 2345 6789` | Solo se buscan celulares que empiezan con 9 | Agregar el formato fijo: `+56` opcional, código de área de 1-2 dígitos y 7-8 dígitos |
| Nombres propios | `Camila Rojas`, `Pedro González` | No hay reconocimiento de nombres | Detección de entidades (NER en español) o, como mínimo, frases como "me llamo", "soy", "mi hija/hijo" seguidas de palabras con mayúscula |
| Direcciones | `Av. Providencia 1234 depto 56` | No hay patrón de direcciones. Los guardrails solo omiten "comuna", "domicilio", "barrio" y "vivo en ..." | Patrón de vía (`av.`, `avenida`, `calle`, `pasaje`) + número, y `depto`/`casa` + número |
| Lugar sin "vivo en" | `soy de La Florida` | Los guardrails solo omiten la frase "vivo en ..." | Lista de comunas de Chile o NER de lugares |
| Fechas de nacimiento | `Nací el 03/05/1980` | No hay patrón de fechas | Enmascarar fechas `dd/mm/aaaa` y `dd-mm-aaaa`, al menos cuando van junto a "nací" o "fecha de nacimiento" |
| Otros identificadores numéricos | número de ficha clínica, pasaporte, patente | No hay patrón | Enmascarar secuencias largas de dígitos que no sean signos vitales |

**Nota:** el patrón de celular no exige un límite de palabra al inicio, así que puede enmascarar
parte de un número más largo. Es un falso positivo menor (sobra un enmascarado), no una
filtración.

Estas mejoras quedan fuera del alcance de S09-8. Se proponen como una tarjeta nueva de mejora
del sanitizador. Las más importantes son los nombres propios, las direcciones y el RUT sin guion.

## Pruebas automáticas relacionadas

`backend/tests/test_payload_ia.py`:

- `test_payload_real_no_lleva_rut_correo_ni_telefono`: un RUT, un correo y un teléfono dentro
  del motivo no aparecen en el payload capturado y sí aparecen sus marcadores.
- `test_otros_formatos_tampoco_viajan`: variantes de formato que el sanitizador sí cubre.
- `test_payload_solo_tiene_campos_del_contrato`: solo viajan `model`, `max_tokens`, `system` y
  `messages`, sin claves de datos personales.
- `test_evaluate_de_punta_a_punta_no_envia_datos_del_paciente` (requiere base): crea un paciente
  con nombre, RUT, dirección, teléfono, correo y fecha de nacimiento, y recorre
  `POST /patients` → `POST /triage/formulario` → `POST /triage/{id}/evaluate`. Comprueba que el
  motivo queda sanitizado en la base, que el payload hacia la IA no lleva ningún dato del
  paciente y que `registro_auditoria.prompt_enviado` es exactamente lo que se envió.