# Levantar MediTriage en local desde cero (S12-1)

Guía probada en Windows (PowerShell + VS Code) con Docker Desktop. Levanta `db` (Postgres),
`redis`, `backend` y `frontend` en tu computador, **sin usar Neon**.

## Requisitos

- Docker Desktop abierto y con **"Engine running"** (`docker version` debe mostrar la sección *Server*).
- Estar en la raíz del repositorio (`Equipo---MediTriage`).

## 1. Crear el `.env`

Copia `.env.example` a `.env` (el `.env` nunca se sube al repo) y deja estos valores:

```env
# Postgres LOCAL del docker compose (host "db", sin SSL)
DATABASE_URL=postgresql://meditriage_app:meditriage_app_dev@db:5432/meditriage_db?sslmode=disable
MIGRATION_DATABASE_URL=postgresql://meditriage_user:meditriage_pass@db:5432/meditriage_db?sslmode=disable

APP_ENCRYPTION_KEY=<clave larga>
APP_RUT_HASH_KEY=<otra clave larga, distinta>
JWT_SECRET=<otra clave larga>
```

- Estas contraseñas de Postgres **son solo de desarrollo** y ya están en el repo:
  `meditriage_app / meditriage_app_dev` sale de `init.sql`, y `meditriage_user / meditriage_pass`
  de `docker-compose.yml`. No son las de Neon que están en el gestor de contraseñas.
- **`JWT_SECRET` no viene en `.env.example`**, pero el backend la exige: agrégala a mano.
- Para generar una clave larga:
  ```powershell
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- Si tienes líneas de Neon (`...neon.tech...`), coméntalas con `#`. Busca "neon" con Ctrl+F para
  asegurarte de que no quede ninguna activa.

## 2. (Opcional) Partir con la base limpia

Si ya habías levantado el proyecto antes, borra los contenedores y el volumen de la base local:

```powershell
docker compose down -v
```

Solo borra el Postgres **local**. No toca Neon, ni el repo, ni las imágenes.

## 3. Levantar los contenedores

```powershell
docker compose up -d --build
docker compose ps
```

- La primera vez tarda ~15 min (sobre todo `npm ci` del frontend). Las siguientes, segundos.
- Con la base vacía, **es normal que el backend se caiga** con
  `RuntimeError: Falta la tabla clave_canario`. Se arregla en el paso 4.

## 4. Correr las migraciones

```powershell
docker compose run --rm backend python -m alembic upgrade head
```

Deben aparecer las 13 líneas `Running upgrade ... -> 0001` hasta `0012 -> 0013`.

- Se usa `run --rm` y no `exec` porque el backend está detenido (paso 3) y `exec` solo funciona
  con contenedores en marcha.

## 5. Volver a levantar el backend

```powershell
docker compose up -d
docker compose logs backend --tail 5
```

Debe decir `Application startup complete`. Revisa la hora de los logs: si corres `logs` justo
después de `up`, puedes ver los del arranque anterior. Espera unos segundos y repite.

## 6. Seeds (usuarios y pacientes de demostración)

Necesitan `SEED_DATABASE_URL` y `DEMO_PASSWORD`, que `docker-compose.yml` no le pasa al backend,
por eso van con `-e`:

```powershell
docker compose run --rm -e SEED_DATABASE_URL="postgresql://meditriage_user:meditriage_pass@db:5432/meditriage_db?sslmode=disable" -e DEMO_PASSWORD="Demo-2026!" backend python -m app.cli seed-roles
```

Resultado: `Seed de roles completado: 3 cuentas demo creadas o actualizadas.`

```powershell
docker compose run --rm -e SEED_DATABASE_URL="postgresql://meditriage_user:meditriage_pass@db:5432/meditriage_db?sslmode=disable" backend python -m app.cli seed-demo
```

Resultado: `Seed demo completado: 2 pacientes sintéticos y sus consentimientos.`

El seed es obligatorio: la migración 0012 deja desactivadas las cuentas demo hasta que corra `seed-roles`.

## 7. Verificar

Abre http://localhost:3000/login (contraseña `Demo-2026!` para todos):

| Usuario | Vista que abre |
|---|---|
| `enfermero@meditriage.test` | `/nurse` |
| `medico@meditriage.test` | `/doctor` |
| `auditor@meditriage.test` | `/auditor` |
| (sin login) | `/waiting-room` |

Si estás conectada con un rol e intentas abrir la vista de otro, te devuelve a la tuya. Es el
control de acceso por rol (`GuardaRol.tsx`), no un error. Para probar otro rol, primero haz clic en **Cerrar sesión**.

## Problemas encontrados

| Síntoma | Causa | Solución |
|---|---|---|
| `alembic upgrade head` no muestra ninguna línea `Running upgrade` | El `.env` apunta a Neon, que ya está migrada | Cambiar las URLs a `@db:5432/meditriage_db?sslmode=disable` y recrear con `docker compose up -d` |
| Para ver a qué base apunta el backend (sin mostrar contraseñas) | — | `docker compose exec backend python -c "import os,urllib.parse as u; [print(k, '->', u.urlparse(os.environ.get(k,'')).hostname) for k in ('DATABASE_URL','MIGRATION_DATABASE_URL')]"` → debe decir `db` |
| `service "backend" is not running` | El backend se cayó por falta de tablas | Paso 4 con `run --rm`, luego paso 5 |
| `RuntimeError: Falta la tabla clave_canario` | Base sin migrar | Paso 4 |
| `APP_ENCRYPTION_KEY no coincide ...` | Base cifrada con otra clave | Usar la clave original, o en local `docker compose down -v` y repetir desde el paso 3 |
| Cambié el `.env` y no se aplica | Docker lee el `.env` al crear los contenedores | `docker compose up -d` (los recrea) |
| `WARN ... the attribute version is obsolete` | Línea `version:` en `docker-compose.yml` | Inofensivo; se puede borrar esa línea |