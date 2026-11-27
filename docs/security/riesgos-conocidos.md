# Riesgos conocidos y límites del MVP – MediTriage

## Objetivo

Documentar los riesgos conocidos y las limitaciones actuales del MVP de MediTriage, considerando su impacto y las medidas de mitigación disponibles.

## Riesgos conocidos

| Riesgo | Impacto | Mitigación actual |
|---|---|---|
| El sanitizador no cubre nombres propios, direcciones ni RUT sin guion. | Posible exposición de datos personales. | Sanitización parcial. Se recomienda evitar datos personales en campos de texto libre. |
| El límite de peticiones reside en la memoria de cada réplica. | No se garantiza un límite global de solicitudes. | Control de peticiones individual por réplica. |
| La IA supera los 1500 ms de respuesta. | La clasificación puede generarse sin utilizar el modelo de IA. | Activación automática del respaldo por reglas. |
| Disponibilidad definida, pero no medida. | No se puede garantizar el cumplimiento del objetivo de disponibilidad. | Objetivo establecido; medición pendiente. |
| Ausencia de pruebas de carga funcionales. | Comportamiento desconocido bajo alta concurrencia. | Pruebas funcionales realizadas; validación de carga pendiente. |

## Riesgos pendientes de la tarjeta S12-7

| Riesgo | Impacto | Mitigación actual |
|---|---|---|
| Paciente sin fecha de nacimiento. | No permite realizar la evaluación ESI. | Registrar la fecha o completarla mediante Editar datos. |
| Staging sin clave de Anthropic. | Las sugerencias se generan mediante reglas y no mediante Claude. | Respaldo por reglas e indicador visual en la interfaz. |
| Pruebas bloqueadas en Windows con localhost. | Dificultades en las pruebas locales. | Utilizar 127.0.0.1 en DATABASE_URL. |
| Usuarios demo inactivos después de la migración 0012. | Algunas pruebas de base de datos pueden omitirse. | Reactivar las cuentas demo en el entorno de pruebas. |
| Archivo backend/.coverage versionado. | Genera modificaciones innecesarias en el repositorio. | Pendiente retirarlo del repositorio y agregarlo a .gitignore. |
| Limitaciones de Docker local. | Problemas de conexión, configuración de IA y disponibilidad inicial de la base de datos. | Verificar los servicios y utilizar el origen autorizado del frontend. |

## Observaciones

Los problemas de sobrescritura del ESI, visualización de casos sin confirmar en el tablero médico e instalación de uvloop fueron corregidos previamente.

El fallo de las pruebas de contrato OpenAPI fue abordado mediante la tarjeta S12-19 (PR #108). El CI fue aprobado, aunque permanecen diferencias documentadas relacionadas con el RUT, las fechas futuras e Idempotency-Key.

Según los resultados de la tarjeta S12-7, no quedaron fallos abiertos que impidan realizar la demostración. Las limitaciones documentadas deberán considerarse antes de avanzar hacia un entorno productivo.

## Referencias

- Tarjeta S12-7.
- docs/testing/s12-7-fallos-demo.md.
- Tarjeta S12-19.
- https://github.com/triageops-ts/Equipo---MediTriage/pull/108
