# ADR OBS - 001 — Agregación de logs (Factor 11)

## Fecha
21/11/2026

## Autores
Lucas Benítez, Kimberlly Guillén, Josefa Rodríguez, Marcela Contreras, Isidora Ramos y Antonia Moya

## 1. Contexto

El backend ya escribe sus logs en JSON por stdout, con un `request_id` por petición y la PII
enmascarada (`backend/app/core/logging_config.py`). Pero cada réplica deja sus logs en su propio
contenedor: con 2 o más réplicas (HPA de 2 a 10) no hay un solo lugar donde buscar una petición,
y los logs se pierden cuando un contenedor se reinicia.

Se necesita un sistema que junte los logs de todas las réplicas y permita buscarlos por `request_id`.

## 2. Opciones consideradas

### Opción A: `kubectl logs` / `docker logs`
- **A favor:** no requiere instalar nada.
- **En contra:** hay que revisar réplica por réplica, se pierden los logs de contenedores
  reiniciados y no hay búsqueda. No cumple el Factor 11.

### Opción B: Servicio gestionado en la nube (CloudWatch Logs u otro)
- **A favor:** no hay que operarlo.
- **En contra:** amarra el proyecto a un proveedor, tiene costo y no se puede demostrar en local.

### Opción C: Loki + Grafana Alloy + Grafana (elegida)
- **A favor:** el proyecto ya usa Prometheus y Grafana, así que Loki se agrega como otra fuente de
  datos en el mismo Grafana. Permite buscar por campos del JSON (`request_id`, `level`). Funciona
  igual en Docker Compose y en Kubernetes.
- **En contra:** es un componente más que operar y respaldar.

## 3. Decisión

Usar **Loki** para guardar los logs, **Grafana Alloy** para recolectarlos desde los contenedores
y **Grafana** para buscarlos.

- **Local / demo:** Loki y Alloy se agregan a `observability/docker-compose.observability.yml`.
- **Kubernetes:** Alloy se despliega como DaemonSet (uno por nodo) y envía los logs de los pods a Loki.

Se usa Alloy y no Promtail porque Grafana declaró Promtail obsoleto y ya no recibe soporte.

## 4. Alternativas descartadas

- **`kubectl logs` / `docker logs` (Opción A):** descartada porque obliga a revisar réplica por réplica, se pierden los logs al reiniciarse un contenedor y no permite buscar por `request_id`.
- **Servicio gestionado en la nube, como CloudWatch Logs (Opción B):** descartado porque amarra el proyecto a un proveedor, tiene costo y no se puede demostrar en local.
- **Promtail como recolector:** descartado porque Grafana lo declaró obsoleto y ya no recibe soporte. Se usa Alloy.
- **Stack ELK (Elasticsearch, Logstash y Kibana):** descartado porque consume bastante más memoria y es más complejo de operar que Loki, y el proyecto ya usa Grafana para sus métricas.

## 5. Consecuencias

- **Positivas:** una sola vista para los logs de todas las réplicas; búsqueda por `request_id`
  para seguir una petición de punta a punta; los logs sobreviven a reinicios de contenedores.
- **Negativas / riesgos:** Loki guarda todo lo que llega, así que si un log trae PII esta queda
  almacenada. Se mitiga con el enmascarado de `logging_config.py`, la regla de Semgrep
  `meditriage-pii-en-logs` y una comprobación en la demo.
- **Retención:** se define en Loki (sugerido 30 días). Los logs técnicos no reemplazan el registro
  de auditoría inmutable en PostgreSQL, que se guarda 5 años por separado.