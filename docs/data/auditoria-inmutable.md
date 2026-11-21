# Auditoría inmutable y escritura automática (S10-4, US-05)

Implementa el diseño de `Arquitectura de Seguridad y Auditoría - MediTriage.docx`
(tabla `registro_auditoria`, bloqueo de UPDATE/DELETE y encadenamiento SHA-256).

## Qué hay
| Pieza | Dónde |
|---|---|
| Tabla, RLS y columnas del contrato | migración `0010` |
| Triggers (hash, bloqueo), REVOKE, verificador | migración `0011` |
| `registrar_evento(...)` y `verificar_cadena(...)` | `backend/app/audit.py` |
| Pruebas | `backend/tests/test_auditoria_db.py` |

## Escritura automática
`registrar_evento(cur, ...)` se llama con el cursor de la **misma transacción** del hecho clínico:

| Endpoint | `evento_tipo` |
|---|---|
| `POST /triage/{id}/evaluate` | `ia.clasificacion.sugerida` o `triage.clasificacion.respaldo_aplicada` (guarda `prompt_enviado` sanitizado) |
| `POST /triage/{id}/decision` | `triage.evaluacion.confirmada` o `triage.override.ejecutado` (guarda `sugerencia_ia`, `decision_final`, `hay_discrepancia`) |
| `POST /triage/{id}/decision/fallo` | `triage.decision.guardar_fallido` |

Si el INSERT del log falla: error 500 y se revierte todo (escenario 🔴 de US-05). Un reintento
idempotente de `/evaluate` no genera un registro nuevo.

## Inmutabilidad
- `meditriage_app` solo tiene `SELECT, INSERT` (UPDATE, DELETE y TRUNCATE revocados).
- Trigger `BEFORE UPDATE OR DELETE` y `BEFORE TRUNCATE`: lanza
  `registro_auditoria es append-only...` (SQLSTATE 42501) para cualquier rol, incluido el dueño.

## Cadena de hashes
`hash_actual = SHA-256( concat_ws('|', hash_anterior, registro_id, episodio_id, decision_id, evento_tipo,
usuario_id_actor, sugerencia_ia, prompt_enviado, decision_final, hay_discrepancia, fecha_hora_evento) )`
(nulos como cadena vacía; fecha con formato `YYYY-MM-DD"T"HH24:MI:SS.US`). El primer registro usa 64 ceros.
El trigger `BEFORE INSERT` calcula `hash_anterior`, `hash_actual` y `fecha_hora_evento` bajo un lock de
asesoría; lo que envíe la aplicación en esas columnas se ignora.

Verificar integridad (vacío = íntegra): `SELECT * FROM verificar_cadena_auditoria();`

## Pendiente (solo documentado)
Particionamiento anual por `fecha_hora_evento` y archivado en frío (WORM) del diseño: no implementado.
Al particionar, hay que recrear los triggers en la tabla padre y revisar el verificador.

## Qué guarda el registro de la inferencia (S10-5)
`prompt_enviado` del evento `ia.clasificacion.sugerida` (o `triage.clasificacion.respaldo_aplicada`) es un texto con este formato:

```
version_prompt: esi-v3 (ab595a512ab7)
modelo: claude-haiku-5-5
fallback_aplicado: no
--- ficha enviada ---
<la ficha exacta que viajó a la IA, sin RUT, correo ni teléfono, sin previsión ni ubicación>
--- respuesta ---
nivel_esi: 2
justificacion: <texto devuelto por el motor>
```

- **Versión del prompt:** constante `VERSION_PROMPT` en `app/ai/engine.py`, con la huella (SHA-256 corto) del prompt del sistema.
  Si alguien edita el prompt sin subir la versión, falla `tests/test_auditoria_prompt.py`.
- **Modelo:** el de `ClasificacionIA.modelo_usado` (o `fallback-rule-engine`).
- No hay columnas aparte en `registro_auditoria`: todo va dentro de `prompt_enviado`, que el hash de la cadena ya cubre.
  Agregar columnas obligaría a cambiar la fórmula del hash y re-encadenar la tabla.
- **Decisión:** el evento de `/decision` guarda `sugerencia_ia`, `decision_final`, `hay_discrepancia` y `decision_id`.
  El motivo escrito por la enfermera queda en `decision_clinica.justificacion`, enlazado por ese `decision_id`
  (texto libre: no se copia al log).
- Si la decisión difiere de la IA quedan **dos registros** (el de la IA no se toca) y `hay_discrepancia = true` en el segundo.
- **Límite conocido:** el texto libre solo se sanitiza para RUT, correo y teléfono; un nombre escrito a mano en el motivo de consulta no se detecta.
