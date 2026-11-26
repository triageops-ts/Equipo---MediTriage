# Plan de recuperación ante desastres (DR) - MediTriage

## 1. Activos protegidos

| Activo | Qué se protege | Método de respaldo o recuperación |
|---|---|---|
| PostgreSQL | Datos clínicos, usuarios, episodios, decisiones y auditoría | Respaldos PostgreSQL en formato CUSTOM con pg_dump y respaldos administrados del proveedor |
| Secretos | Credenciales, JWT_SECRET, APP_ENCRYPTION_KEY y claves de conexión | Almacenamiento seguro fuera de Git, con copia protegida y acceso restringido |
| Imágenes de contenedores | Imágenes del backend y frontend | GitHub Container Registry (GHCR), identificadas mediante tags y digests |
| Manifiestos | Configuración Kubernetes y Docker, políticas y despliegues | Repositorio Git remoto, historial de commits y ramas protegidas |

No se deben almacenar contraseñas, tokens ni archivos .env con secretos en el repositorio.

## 2. Objetivos RPO y RTO

Objetivos iniciales propuestos para validar con el equipo:

- RPO: máximo 24 horas de pérdida de datos para PostgreSQL.
- RTO: máximo 4 horas para recuperar el servicio principal de MediTriage.

Estos valores son objetivos de planificación, no resultados medidos ni garantías del proveedor.

## 3. Procedimiento de respaldo PostgreSQL

- Herramienta: pg_dump 18.7.
- Formato: CUSTOM.
- Archivo de prueba: meditriage-backup.dump.
- Origen: base Neon de desarrollo (neondb).
- Fecha: 25-11-2026.
- Tamaño: 143.300 bytes.

El archivo de respaldo se mantuvo fuera del repositorio, en C:\MediTriage-DR.

## 4. Prueba de restauración PostgreSQL

- Destino: PostgreSQL 18 aislado en Docker.
- Base de destino: meditriage_dr_restore.
- Resultado: restauración exitosa.

Verificaciones realizadas:

- Rol meditriage_app presente.
- 27 políticas RLS recuperadas.
- Migración Alembic: 0013.
- Función verificar_cadena_auditoria(): 0 registros con error.
- Restauración finalizada sin errores.

Incidencia encontrada:
El respaldo no incluye roles globales de PostgreSQL. La primera restauración requirió crear el rol meditriage_app en el servidor de recuperación. Después se restauró nuevamente la base vacía y la operación finalizó correctamente.

## 5. Game Day: recuperación de Redis

### Prueba local

Fecha: 25-11-2026.
Entorno: Docker Compose local.
Tipo de falla: detención controlada del contenedor Redis.

- Inicio de medición de la falla: 16:37:10.
- Comando de recuperación: docker compose start redis.
- Redis respondió PONG.
- Backend respondió HTTP 200 y healthy.
- Fin de recuperación: 16:39:17.
- Tiempo medido: 2 minutos y 6,85 segundos.

Resultado: recuperación local exitosa.

### Prueba en staging

Fecha: 25-11-2026.
Entorno: VM staging, namespace triageops-staging.
Tipo de falla: eliminación controlada del pod Redis.

Estado inicial:
- Deployment redis: 1/1 disponible.
- Backend: 2/2 disponible.
- Frontend: 2/2 disponible.
- Inicio de la prueba: 23:44:24 UTC.

Falla simulada:
- Se eliminó el pod redis-58d9bdbf-dx2q6 mediante kubectl delete pod.
- Kubernetes creó automáticamente el nuevo pod redis-58d9bdbf-mt9z4.
- El nuevo pod alcanzó estado 1/1 Running.

Verificación de recuperación:
- Comprobación final de pods: 23:48:05 UTC.
- Tiempo total desde la falla hasta la comprobación final: 3 minutos y 41 segundos.
- Backend respondió HTTP 200 OK.
- Estado del servicio: healthy.

Resultado: recuperación exitosa en staging. Kubernetes recreó Redis y el backend continuó respondiendo correctamente.
## 6. Runbooks

Procedimiento utilizado:
ops/runbooks/redis-recovery.md

El procedimiento contempla revisar el estado de los servicios, iniciar Redis, comprobar PONG y verificar la salud del backend.

## 7. Evidencias

Las capturas de las pruebas se almacenan en docs/img/.

## 8. Pendientes

- Validar los objetivos RPO y RTO con el equipo.
- Comunicar los resultados del Game Day al responsable de la tarjeta 12.
