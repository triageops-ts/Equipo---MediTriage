# Recuperación de Redis - MediTriage

## Alcance
Procedimiento para recuperar Redis en:
- Entorno local Docker Compose.
- Entorno staging Kubernetes, namespace triageops-staging.

## Recuperación local (Docker Compose)

### Falla simulada
Contenedor meditriage-redis detenido o servicio Redis sin responder.

1. Revisar el estado:
   docker compose ps -a

2. Iniciar Redis:
   docker compose start redis

3. Comprobar Redis:
   docker exec meditriage-redis redis-cli ping

   Resultado esperado: PONG.

4. Comprobar el backend:
   Invoke-WebRequest http://localhost:8000/api/v1/health -UseBasicParsing

   Resultado esperado: HTTP 200 y estado healthy.

## Recuperación en staging (Kubernetes)

### Falla simulada
Pod Redis detenido, eliminado o sin responder en el namespace triageops-staging.

1. Conectarse a la VM staging mediante SSH autorizado.

2. Revisar el estado:
   kubectl get pods
   kubectl get deploy redis

3. Si el pod Redis está fallando, identificar el pod actual y eliminarlo para que Kubernetes lo recree:
   kubectl delete pod <nombre-del-pod-redis>

   Ejecutar esta acción solo con autorización y después de notificar al equipo.

4. Observar la recuperación:
   kubectl get pods -w

   Resultado esperado: un nuevo pod Redis en estado 1/1 Running.

5. Comprobar el estado final:
   kubectl get pods
   kubectl get deploy

6. Desde PowerShell local, verificar el backend:
   Invoke-WebRequest `
     -Uri "https://coherent-mop-voltage.ngrok-free.dev/api/v1/health" `
     -Headers @{"ngrok-skip-browser-warning"="true"} `
     -UseBasicParsing

   Resultado esperado: HTTP 200 y estado healthy.

## Si la recuperación falla

- Local: revisar los registros con docker compose logs --tail 50 redis.
- Staging: revisar los pods con kubectl describe pod <nombre-del-pod-redis> y los registros con kubectl logs <nombre-del-pod-redis>.
- No eliminar volúmenes ni recrear la base de datos.
- No modificar réplicas ni recursos administrados por Argo CD sin autorización.
- Registrar el error y escalar al responsable técnico.

## Evidencias
Guardar capturas del estado inicial, falla simulada y recuperación en docs/img/.

Registrar fecha y tiempo real de recuperación en docs/dr-plan.md.

## Resultados del Game Day
El 25-11-2026 se realizó una prueba local y otra en staging.
En staging, Kubernetes recreó automáticamente el pod Redis y el backend respondió HTTP 200 (healthy).
El tiempo desde la eliminación del pod hasta la comprobación final fue de 3 minutos y 41 segundos.

