# SLIs, SLOs y error budget — MediTriage Backend

Este documento define cómo medimos que el backend de MediTriage funciona bien y qué hacemos cuando deja de hacerlo. Las métricas salen de la instrumentación OpenTelemetry (`backend/app/core/telemetry.py`) y se consultan en Prometheus (kube-prometheus-stack).

## 1. Contexto del servicio

| | |
|---|---|
| **Servicio** | `meditriage-backend` (FastAPI), namespace `triageops`, 2 a 10 réplicas (HPA) |
| **Quién lo usa** | Enfermería de triage, médicos de turno y auditoría, desde el frontend |
| **Flujo crítico** | Login → registrar paciente (`POST /api/v1/patients`) → enviar formulario clínico y recibir la sugerencia ESI (`POST /api/v1/triage/formulario`) → guardar la decisión final (`POST /api/v1/triage/{episodio_id}/decision`) |
| **Por qué importa** | En urgencias, un triage que no responde o responde tarde retrasa la atención de pacientes graves. El requisito del proyecto es responder en menos de 3 s (CHARTER, DoD 4). |

**Alcance de las mediciones**

- **Dentro:** todas las rutas HTTP de la API (`/api/v1/auth/*`, `/api/v1/patients*`, `/api/v1/triage/*`).
- **Fuera:** `GET /api/v1/health` (lo consultan las probes de Kubernetes cada 10 s y 20 s por réplica; inflaría el conteo y haría ver mejor al servicio de lo que es), el WebSocket `/api/v1/ws/tablero` (el middleware solo mide peticiones HTTP), las rutas que no existen (`route="unmatched"`, escaneos y bots) y el frontend.
- **Proveedor de IA:** si el modelo falla o tarda más de 1,5 s, el backend responde con reglas heurísticas. Para el usuario el servicio sigue respondiendo, así que ese caso cuenta como bueno mientras la respuesta llegue a tiempo.

## 2. Métricas de origen

| Métrica (Prometheus) | Tipo | Etiquetas |
|---|---|---|
| `meditriage_http_requests_total` | contador | `method`, `route`, `status_code` |
| `meditriage_http_request_duration_seconds_bucket` / `_count` / `_sum` | histograma | `method`, `route`, `status_code`, `le` |

- `route` es la plantilla (`/api/v1/patients/{rut}`), nunca la URL con valores. No hay identificadores de pacientes en ninguna etiqueta.
- Los límites del histograma son: 0,005 · 0,01 · 0,025 · 0,05 · 0,1 · 0,25 · 0,5 · 1 · 2 · **3** · 5 · 10 segundos. El límite `le="3"` cuenta las peticiones que terminaron en 3 s o menos.
- Estos nombres son los que genera el exporter de Prometheus a partir de `meditriage.http.requests` y `meditriage.http.request.duration` (unidad `s`). Se confirman con `kubectl -n triageops port-forward deploy/meditriage-backend 9464:9464` y `curl -s localhost:9464/metrics | grep meditriage_`.

> **Retención:** las consultas de abajo usan una ventana de 30 días. kube-prometheus-stack guarda 10 días por defecto, así que hay que subir `prometheus.prometheusSpec.retention` a `35d` (o más) en los valores de Helm. Si no, el SLI de 30 días se calcula con solo 10 días de datos.

## 3. SLI y SLO de disponibilidad

**SLI:** proporción de peticiones válidas que el servicio atendió sin error del servidor.

```
SLI_disponibilidad = eventos buenos / eventos válidos     (ventana móvil de 30 días)
```

| Elemento | Definición |
|---|---|
| **Evento válido** | Petición HTTP a una ruta de la API, excluyendo `/api/v1/health` y `unmatched`. |
| **Evento bueno** | Evento válido con `status_code` distinto de 5xx. Los 4xx (401, 403, 404, 409, 422) cuentan como buenos: el servicio respondió bien a una petición incorrecta del cliente. |
| **Evento malo** | Evento válido con `status_code` 5xx, incluidas las excepciones no controladas (se registran como 500). |
| **Ventana** | 30 días móviles. |
| **Fuente** | `meditriage_http_requests_total`, en Prometheus. |

```promql
# SLI de disponibilidad (30 d)
1 - (
  sum(increase(meditriage_http_requests_total{route!~"/api/v1/health|unmatched", status_code=~"5.."}[30d]))
  /
  sum(increase(meditriage_http_requests_total{route!~"/api/v1/health|unmatched"}[30d]))
)
```

**SLO de disponibilidad: 99,5 % de los eventos válidos son buenos, medido en 30 días.**

Es el 99,5 % mensual que fijan los ADR 0001 y 0002. Equivale a unas 3 h 36 min de indisponibilidad total en 30 días.

## 4. SLI y SLO de latencia

**SLI:** proporción de peticiones atendidas que respondieron en 3 s o menos.

```
SLI_latencia = eventos buenos / eventos válidos     (ventana móvil de 30 días)
```

| Elemento | Definición |
|---|---|
| **Evento válido** | Petición HTTP a una ruta de la API, excluyendo `/api/v1/health` y `unmatched`, y excluyendo las 5xx (esas ya cuentan en disponibilidad; así un mismo fallo no se penaliza dos veces). |
| **Evento bueno** | Evento válido cuya duración fue **≤ 3 s**, es decir, que cae en el bucket `le="3"`. |
| **Evento malo** | Evento válido que tardó más de 3 s. |
| **Ventana** | 30 días móviles. |
| **Fuente** | `meditriage_http_request_duration_seconds_bucket{le="3"}` y `meditriage_http_request_duration_seconds_count`, en Prometheus. |

```promql
# SLI de latencia (30 d)
sum(increase(meditriage_http_request_duration_seconds_bucket{le="3", route!~"/api/v1/health|unmatched", status_code!~"5.."}[30d]))
/
sum(increase(meditriage_http_request_duration_seconds_count{route!~"/api/v1/health|unmatched", status_code!~"5.."}[30d]))
```

**SLO de latencia: 95 % de los eventos válidos responden en 3 s o menos, medido en 30 días.**

El umbral de 3 s viene del requisito del CHARTER y del ADR de IA. El 95 % deja margen para picos del proveedor de IA sin esconder un problema sostenido. (`docs/arch/atributos-calidad.md` menciona un objetivo interno de p95 < 200 ms; es una meta de rendimiento de diseño y no un SLO de este documento.)

## 5. Error budget

El error budget es la cantidad de eventos malos que podemos tener en la ventana sin incumplir el SLO.

```
error_budget = (1 − SLO) × eventos_válidos
```

**Ejemplo numérico** (30 días con 200.000 peticiones válidas; se usa el mismo total para los dos SLO para simplificar):

| | Disponibilidad | Latencia |
|---|---|---|
| SLO | 99,5 % | 95 % |
| Cálculo | (1 − 0,995) × 200.000 | (1 − 0,95) × 200.000 |
| **Error budget** | **1.000 peticiones con 5xx** | **10.000 peticiones de más de 3 s** |
| Eventos malos al día 20 | 420 | 4.000 |
| Budget consumido | 420 / 1.000 = **42 %** | 4.000 / 10.000 = **40 %** |
| Budget restante | 580 peticiones | 6.000 peticiones |

```promql
# Fracción de budget de disponibilidad consumida (1 = agotado)
(
  sum(increase(meditriage_http_requests_total{route!~"/api/v1/health|unmatched", status_code=~"5.."}[30d]))
  /
  sum(increase(meditriage_http_requests_total{route!~"/api/v1/health|unmatched"}[30d]))
) / (1 - 0.995)
```

El budget se recalcula todos los días con la ventana móvil: los errores de hace más de 30 días dejan de contar.

## 6. Política cuando el budget se agota

| Budget consumido (cualquiera de los dos SLO) | Qué pasa |
|---|---|
| **< 50 %** | Operación normal. Se despliega con el flujo habitual (PR, revisión y GitOps). |
| **50 % – 99 %** | Alerta al equipo por Discord. Se revisa en la reunión de los lunes qué consumió el budget. Los cambios riesgosos se despliegan con cuidado extra y se vigila el SLI después del despliegue. |
| **≥ 100 % (agotado)** | **Congelamiento de despliegues de funcionalidades nuevas** hasta que el SLI vuelva a cumplir el SLO. Solo se despliegan correcciones de fiabilidad, parches de seguridad y rollbacks. El equipo prioriza arreglar la causa (el tech lead decide qué tarjetas pasan primero). Se escribe un postmortem breve con causa, impacto y acciones, sin datos personales de pacientes. |
| **Vuelve al SLO** | Se levanta el congelamiento y se registran las acciones de prevención en el backlog. |

Excepciones: una corrección crítica de seguridad (CVE explotable, fuga de PII) se despliega aunque el budget esté agotado, con aprobación del tech lead y de DevSecOps.

### Sin tráfico = sin datos

Un servicio sin peticiones no cumple ni incumple el SLO: no hay eventos que medir. Reglas:

- Si en la ventana hay **menos de 1.000 eventos válidos**, el SLI se informa como **«sin datos suficientes»**. No se muestra 100 % ni 0 %, no se calcula el budget y no se activa la política de arriba. Pasa en un ambiente de práctica o justo después de un despliegue nuevo.
- Cuando `sum(increase(...[30d]))` devuelve vacío, el panel de Grafana debe mostrar «sin datos» y no cero.
- Que haya cero tráfico en horas de turno no es buena noticia: puede ser una caída en la que las peticiones ni siquiera llegan al servicio. Para ese caso se mantiene una alerta por el target del servicio dejando de aparecer `up` en Prometheus.
