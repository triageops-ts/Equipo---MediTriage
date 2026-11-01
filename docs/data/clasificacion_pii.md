# Clasificación de campos: PII vs. clínicos (Tarjeta S04-2)


**Regla general para la IA:** solo salen campos clínicos codificados, asociados al
`token_correlacion_efimero`. Nunca sale PII directa, fecha de nacimiento exacta ni texto libre sin sanitizar.

**Categorías:** PII directa (identifica a la persona) · Cuasi-identificador (identifica al combinarse
con otros datos) · Credencial · Clínico · Técnico (ids, fechas internas, auditoría).

## paciente

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| paciente_id | Técnico | No (se usa el token efímero) | No | — |
| nombre_completo | PII directa | **No** | **No (texto plano)** | Cifrar (`bytea`), igual que `rut` |
| rut | PII directa | **No** | Sí | — |
| fecha_nacimiento | Cuasi-identificador | **No** exacta (solo edad o rango etario) | **No** | Decidir: cifrar, o dejar en claro y no exponerla en la API |
| sexo_biologico | Clínico | Sí | No | — |

## consentimiento

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| consentimiento_id, paciente_id | Técnico | No | No | — |
| tipo_consentimiento, otorgado, version_texto | Legal/administrativo | No | No | — |
| fecha_hora | Técnico | No | No | — |
| firma_digital | Sensible (prueba legal) | No | `bytea` | Confirmar si es un hash/firma o la imagen de la firma |

## contacto_paciente

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| paciente_id | Técnico | No | No | — |
| direccion, telefono, email | PII directa | **No** | Sí | — |

## contacto_emergencia

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| contacto_id, paciente_id | Técnico | No | No | — |
| nombre | PII directa (de un tercero) | **No** | **No (texto plano)** | Cifrar |
| telefono | PII directa (de un tercero) | **No** | **No (texto plano)** | Cifrar, igual que `contacto_paciente.telefono` |
| relacion | Cuasi-identificador | No | No | — |

## usuario_staff

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| usuario_id, rol, activo | Técnico | No | No | — |
| nombre_completo | PII directa | No | **No (texto plano)** | Cifrar o aceptar el riesgo (es personal del hospital) |
| rut, email | PII directa | No | Sí | — |
| contraseña | Credencial | No | `bytea` | Debe ser un **hash lento** (argon2/bcrypt), no un cifrado reversible. Si el login es por Keycloak, evaluar si este campo hace falta |

## episodio_triage

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| episodio_id, paciente_id, usuario_id, estado | Técnico | No | No | — |
| fecha_hora_ingreso | Técnico | No | No | — |
| motivo_consulta_texto_libre | **Riesgo de PII** (texto libre) | **No**, salvo sanitizado | No | Pasar por el módulo de anonimización antes de enviarlo; evaluar cifrarlo |

## signos_vitales

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| presion_sistolica, presion_diastolica, frecuencia_cardiaca, frecuencia_respiratoria, temperatura, saturacion_oxigeno, escala_dolor, nivel_conciencia | Clínico | **Sí** | No | — |
| signos_vitales_id, episodio_id | Técnico | No | No | — |
| fecha_hora_medicion | Técnico | No | No | — |

## sintomas

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| codigo_sintoma, severidad, antecedentes_relevantes_codificados | Clínico codificado | **Sí** | No | — |
| alergias | Clínico | Sí, **solo si es un valor codificado** | No | Si admite texto libre, tratarlo como `motivo_consulta_texto_libre` |
| sintoma_id, episodio_id | Técnico | No | No | — |

## clasificacion_ia

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| token_correlacion_efimero | Técnico | **Sí**, es la única clave que viaja | No | No debe poder vincularse al `paciente_id` fuera de la base |
| nivel_esi_sugerido, justificacion_ia | Respuesta de la IA | (viene de la IA) | No | — |
| modelo_usado, hash_datos_enviados_ia | Técnico (trazabilidad) | No | No | — |
| tiempo_solicitud, tiempo_respuesta | Técnico | No | No | — |
| clasificacion_id, episodio_id | Técnico | No | No | — |

## decision_clinica

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| nivel_esi_final, justificacion | Clínico | No | No | — |
| coincide_con_ia | Derivado | No | No | Está en la base, pero se puede calcular comparando con `clasificacion_ia` (ver nota de 3FN) |
| decision_id, episodio_id, usuario_id, fecha_hora_decision | Técnico | No | No | — |

## registro_auditoria

| Campo | Categoría | ¿Va a la IA? | Cifrado hoy | Acción |
|---|---|---|---|---|
| detalle_json | Técnico, **riesgo de PII** | No | No | No guardar PII dentro del JSON (solo ids y tipo de evento) |
| registro_id, evento_tipo, entidad_afectada, entidad_id, usuario_id, fecha_hora_evento | Técnico | No | No | — |
| hash_anterior, hash_actual | Técnico (cadena de integridad) | No | No | — |

## Resumen de lo que falta cifrar (para Isidora)

1. `paciente.nombre_completo`
2. `contacto_emergencia.nombre` y `contacto_emergencia.telefono`
3. `paciente.fecha_nacimiento` (decidir)
4. `episodio_triage.motivo_consulta_texto_libre` (decidir)
5. `usuario_staff.nombre_completo` (decidir)
6. Revisar que `usuario_staff.contraseña` sea un hash y no un cifrado reversible
