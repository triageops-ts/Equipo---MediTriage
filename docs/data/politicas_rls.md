# Políticas de Row-Level Security (Tarjeta S04-2)

Implementadas en `migrations/versions/0002_paciente_consentimiento_rls.py` y probadas con
`tests/test_rls.sql`.

## Cómo funciona

1. Keycloak autentica al usuario. El backend valida el token y saca de él el **rol** y el **id**.
2. Al inicio de cada transacción, el backend llama a `set_rls_context(conn, rol, usuario_id)` (en `db.py`),
   que fija las variables `app.rol` y `app.usuario_id`. Duran solo hasta el commit/rollback.
3. Las políticas leen `app.rol`. Si no se fijó, o el rol no es uno de los tres válidos, **no se ve ni se escribe nada**.
4. La app se conecta con el rol de base de datos `meditriage_app` (sin `BYPASSRLS`). El usuario `neondb_owner`
   se salta el RLS, por eso **solo debe usarse para migraciones**, nunca en la app.

## Quién puede qué

| Tabla | enfermero | medico | auditor |
|---|---|---|---|
| paciente | Leer, crear, modificar | Leer | Sin acceso |
| contacto_paciente | Leer, crear, modificar | Leer | Sin acceso |
| contacto_emergencia | Leer, crear, modificar | Leer | Sin acceso |
| consentimiento | Leer, **registrar** | Leer | Leer |

Reglas que valen para todos los roles:
- **Nadie puede borrar** filas de estas tablas (no hay permiso `DELETE`).
- **`consentimiento` no se modifica** (no hay permiso `UPDATE`). Para revocar un consentimiento se inserta una fila nueva con `otorgado = false`; el historial queda completo.
- El auditor ve consentimientos para verificarlos, pero no los datos personales del paciente.

## Decisiones que el equipo puede cambiar

- ¿El médico debe poder corregir datos del paciente? Hoy solo lee. Para permitirlo, basta ampliar la política `*_update`.
- ¿El enfermero debe ver solo los pacientes de sus propios episodios? Hoy ve todos. Eso requeriría una política que consulte `episodio_triage` (usaría `app.usuario_id`).
- ¿El auditor necesita ver pacientes? Hoy no. Si lo necesita, debería ser con datos anonimizados (una vista), no con la tabla directa.

## Qué hay que hacer una sola vez en Neon (fuera del repo)

Después de migrar, la contraseña del rol de la app se define a mano, no en el repo:

```sql
ALTER ROLE meditriage_app WITH LOGIN PASSWORD '<contraseña-larga>';
```

Luego el backend usa un `DATABASE_URL` con ese usuario (`meditriage_app`), y Alembic sigue usando el del dueño.
La contraseña va en variables de entorno, nunca en el código.
