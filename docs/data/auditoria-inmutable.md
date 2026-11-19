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
