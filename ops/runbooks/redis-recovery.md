# Recuperación de Redis - MediTriage

## Alcance
Procedimiento para recuperar Redis en el entorno local Docker Compose.

## Falla simulada
Contenedor meditriage-redis detenido o servicio Redis sin responder.

## Recuperación

1. Revisar el estado de los servicios:
   docker compose ps -a

2. Iniciar Redis:
   docker compose start redis

3. Comprobar que Redis responde:
   docker exec meditriage-redis redis-cli ping

   Resultado esperado: PONG.

4. Comprobar que el backend continúa saludable:
   Invoke-WebRequest http://localhost:8000/api/v1/health -UseBasicParsing

   Resultado esperado: HTTP 200 y estado healthy.

## Si la recuperación falla

- Revisar los registros:
  docker compose logs --tail 50 redis

- No eliminar volúmenes ni recrear la base de datos.
- Registrar el error y escalar al responsable técnico.

## Evidencias
Guardar capturas del estado inicial, falla simulada y recuperación en docs/img/.

Registrar fecha y tiempo real de recuperación en docs/dr-plan.md.

## Limitación
Este procedimiento corresponde a una prueba local con Docker Compose.
No acredita una recuperación en un entorno staging.
