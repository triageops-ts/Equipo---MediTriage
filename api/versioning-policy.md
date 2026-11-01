# Política de versionado de la API de MediTriage

## 1. Versionado

La API utiliza versionado en la ruta. La versión actual es `/api/v1`.

## 2. Cambios incompatibles

Se consideran incompatibles eliminar endpoints, cambiar tipos de datos, renombrar campos existentes o agregar campos obligatorios que afecten a los clientes actuales. Estos cambios requieren una nueva versión mayor, por ejemplo `/api/v2`.

## 3. Deprecación

Las versiones que serán retiradas se anunciarán en la documentación con al menos 6 meses de anticipación, salvo situaciones críticas de seguridad o legales.

## 4. Compatibilidad

Cada versión debe mantener su documentación OpenAPI y ejemplos de solicitudes y respuestas actualizados.
