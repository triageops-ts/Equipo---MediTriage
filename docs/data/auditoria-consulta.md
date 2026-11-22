# Consulta de la auditoría (S10-6)

Vista y endpoints de solo lectura para el rol **auditor** (US-05).

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/audit-logs` | Historial, del más reciente al más antiguo. Filtros: `episodio_id`, `usuario_id`, `hay_discrepancia`. Paginación: `skip` (0 por defecto) y `limit` (20 por defecto, máximo 100). |
| GET | `/api/v1/audit-logs/verificacion` | Recorre la cadena de hashes. Responde `valida`, `registros_verificados` y, si está rota, `primer_registro_alterado` (id y motivo). |

- Solo el rol `auditor`: sin sesión es 401 y con otro rol es 403 (el chequeo ocurre antes de abrir la conexión a la base).
- No existen POST, PUT, PATCH ni DELETE sobre `/audit-logs` (405). La tabla además es inmutable en la base (migración 0011).
- La política RLS `registro_auditoria_select` ya permitía leer al auditor; no hay migración nueva.

## Primer registro alterado

`verificar_cadena_auditoria()` devuelve los registros rotos sin orden. El endpoint los ordena como la cadena
(`fecha_hora_evento`, `registro_id`) y toma el primero. Un registro alterado marca también al siguiente
(su `hash_anterior` ya no cuadra), así que el primero de la lista es el que realmente se tocó.

## Vista del auditor (`/auditor`)

Tabla de solo lectura (sin botones de editar ni borrar) con fecha UTC, evento, episodio, actor, sugerencia de la IA,
decisión final y la marca **Modificado manualmente** (`hay_discrepancia`). Cada fila tiene un detalle con el
prompt registrado (versión del prompt, modelo y respuesta) y los dos hashes. Incluye filtros, paginación y el
botón «Verificar integridad de la cadena».

## Pruebas

- `tests/test_audit_logs.py`: roles, filtros, paginación y 405 en escritura, sin base de datos.
- `tests/test_audit_logs_db.py`: contra Postgres real (solo en una rama de pruebas). La prueba de cadena rota
  altera un registro dentro de una transacción que se deshace; no deja nada alterado.
