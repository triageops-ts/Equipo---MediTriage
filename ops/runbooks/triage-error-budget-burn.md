# Runbook: MediTriage Error Budget Burn

> **ADVERTENCIA: USO EXCLUSIVO EN LABORATORIO.**
> Esta simulación utiliza métricas sintéticas y servicios aislados.
> No representa una degradación real del backend.
> No ejecutar comandos kubectl ni modificar el entorno activo `triageops`.

## 1. Confirmar la alerta

Abrir `http://localhost:19090/alerts` y comprobar que `MediTriageErrorBudgetBurn` aparece en estado `firing`.

Consultar también la API de Prometheus:

```powershell
Invoke-RestMethod "http://localhost:19090/api/v1/alerts" | ConvertTo-Json -Depth 10
```

Verificar que la alerta tenga la etiqueta `severity=page`.

## 2. Diagnosticar el laboratorio

Comprobar que los servicios aislados estén activos:

```powershell
docker compose -f ".\observability\lab\docker-compose.lab.yml" ps
```

Revisar los registros de Prometheus y Alertmanager:

```powershell
docker compose -f ".\observability\lab\docker-compose.lab.yml" logs --tail=60 prometheus alertmanager
```

## 3. Revisar los indicadores SLI

Consultar en Prometheus los siguientes indicadores:

- `meditriage:availability_error:ratio_rate5m`
- `meditriage:availability_error:ratio_rate1h`
- `meditriage:latency_error:ratio_rate5m`
- `meditriage:latency_error:ratio_rate1h`

Abrir `http://localhost:19090/graph` y comparar los resultados con los umbrales definidos en `observability/prometheus/rules.yml`.

La prueba utiliza valores sintéticos publicados en Pushgateway. No mide solicitudes reales ni latencia efectiva del backend.

## 4. Aplicar mitigación en el laboratorio

Retirar exclusivamente las métricas sintéticas del grupo `burn-lab`:

```powershell
Invoke-WebRequest `
    -Uri "http://localhost:19091/metrics/job/burn-lab" `
    -Method Delete `
    -UseBasicParsing
```

Esta acción elimina las métricas de prueba y no modifica los servicios activos de MediTriage.

## 5. Verificar recuperacion

Esperar a que Prometheus actualice las metricas y el estado de la alerta:

```powershell
Start-Sleep -Seconds 40

Invoke-RestMethod "http://localhost:19090/api/v1/alerts" |
    ConvertTo-Json -Depth 10
```

Comprobar las notificaciones recibidas:

```powershell
docker compose -f ".\observability\lab\docker-compose.lab.yml" logs --tail=100 webhook-sink
```

La recuperacion se considera verificada cuando la alerta deja de estar en estado `firing` y el receptor registra la notificacion de resolucion.

## 6. Registrar el incidente y la evidencia

Documentar:

- Fecha y hora de la simulacion.
- Alerta generada y severidad.
- Metricas sinteticas utilizadas.
- Diagnostico realizado.
- Mitigacion aplicada.
- Resultado de la recuperacion.
- Confirmacion de la notificacion recibida.

Guardar una captura real de Prometheus mostrando la alerta disparada en:

`docs/img/alerta-pagina.png`

No crear capturas ficticias ni afirmar que una alerta se disparo o resolvio sin evidencia verificable.

Al finalizar la prueba y guardar la evidencia, detener exclusivamente los servicios del laboratorio:

```powershell
docker compose -f ".\observability\lab\docker-compose.lab.yml" down
```

**Restriccion final:** No ejecutar comandos de rollback, no utilizar `kubectl` y no modificar el despliegue activo `triageops`.