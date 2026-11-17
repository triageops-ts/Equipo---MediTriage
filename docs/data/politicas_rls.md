# Políticas de Row-Level Security (Tarjetas S04-2 y S09-2)

Implementadas en `migrations/versions/0002_paciente_consentimiento_rls.py` (paciente, contactos y
consentimiento) y `migrations/versions/0008_rls_triage.py` (tablas de triage). La 0008 también deja
el rol, los permisos y las políticas de las tablas base de forma repetible, por si una base nunca
recibió el RLS de la 0002. Se prueban con `tests/test_rls_db.py`.

## Cómo funciona

1. El backend valida el token y saca de él el **rol** y el **id** del usuario.
2. `get_conn` (en `app/db.py`) abre la conexión y llama a `set_rls_context(conn, rol, usuario_id)`,
   que fija `app.rol` y `app.usuario_id` con `set_config(..., true)` (equivale a `SET LOCAL`).
   Duran solo hasta el commit o rollback de esa transacción, así que no pasan a otra petición.
3. Las políticas leen `app.rol` con la función `app_rol()` (y `app_usuario_id()` para la fila propia).
   Si no se fijó, o el rol no es uno de los válidos, **no se ve ni se escribe nada**.
4. El login aún no tiene token: usa `get_conn_login`, que fija el rol interno `autenticacion`.
   Ese rol solo puede leer `usuario_staff` (para buscar al usuario por correo).
5. La app se conecta con el rol de base de datos `meditriage_app` (sin `BYPASSRLS`). El usuario dueño
   se salta el RLS, por eso **solo se usa para migrar**, con la variable `MIGRATION_DATABASE_URL`.
   La app usa `DATABASE_URL`.

## Quién puede qué

| Tabla | enfermero | medico | auditor |
|---|---|---|---|
| paciente | Leer, crear, modificar | Leer | Sin acceso |
| contacto_paciente | Leer, crear, modificar | Leer | Sin acceso |
| contacto_emergencia | Leer, crear, modificar | Leer | Sin acceso |
| consentimiento | Leer, **registrar** | Leer | Leer |
| usuario_staff | Leer solo su propia fila | Leer solo su propia fila | Leer solo su propia fila |
| episodio_triage | Leer, crear, actualizar | Leer | Sin acceso |
| signos_vitales | Leer, crear | Leer | Sin acceso |
| sintomas_triage | Leer, crear | Leer | Sin acceso |
| clasificacion_ia | Leer, crear | Leer | Leer |
| decision_clinica | Leer, **registrar** | Leer | Leer |

Reglas que valen para todos los roles:
- **Nadie puede borrar** filas de estas tablas (no hay permiso `DELETE`).
- **`consentimiento`, `clasificacion_ia` y `decision_clinica` no se modifican** (no hay permiso
  `UPDATE`). Para revocar un consentimiento se inserta una fila nueva con `otorgado = false`.
- El auditor ve consentimientos, clasificaciones de la IA y decisiones para auditarlas, pero no los
  datos personales del paciente ni los episodios.
- `episodio_triage` permite `UPDATE` al enfermero porque el backend bloquea la fila con
  `SELECT ... FOR UPDATE` al registrar la decisión.

## Decisiones que el equipo puede cambiar

- ¿El médico debe poder corregir datos del paciente? Hoy solo lee. Para permitirlo, basta ampliar la política `*_update`.
- ¿El enfermero debe ver solo los pacientes de sus propios episodios? Hoy ve todos. Eso requeriría una política que consulte `episodio_triage` (usaría `app.usuario_id`).
- ¿El auditor necesita ver pacientes? Hoy no. Si lo necesita, debería ser con datos anonimizados (una vista), no con la tabla directa.
- `clasificacion_ia` hoy la escribe el enfermero. Cuando el motor de IA guarde sus resultados, hay que decidir si lo hace con el contexto del enfermero o con un rol propio.

## Qué hay que hacer una sola vez en Neon (fuera del repo)

Después de migrar, la contraseña del rol de la app se define a mano, no en el repo:

```sql
ALTER ROLE meditriage_app WITH LOGIN PASSWORD '<contraseña-larga>';
```

Luego el backend usa un `DATABASE_URL` con ese usuario (`meditriage_app`), y Alembic usa
`MIGRATION_DATABASE_URL` (el dueño). Las contraseñas van en variables de entorno, nunca en el código.

## Pruebas

`tests/test_rls_db.py` se conecta como `meditriage_app`, siembra datos como enfermero dentro de una
transacción que se revierte, y comprueba para cada rol qué tablas ve, qué puede escribir, que nadie
borra y que `usuario_staff` solo muestra la fila propia. Se omite si no hay `DATABASE_URL`.