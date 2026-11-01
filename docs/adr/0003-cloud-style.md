# ADR 0003: Elección de estilo cloud

## Fecha
10/09/26

## Autores
Josefa Rodriguez, Lucas Benítez, Marcela Contreras, Isidora Ramos, Antonia Moya y Kimberlly Guillén

---
## Contexto

El sistema MediTriage está diseñado para gestionar la clasificación y priorización de pacientes en entornos clínicos de urgencia. En este escenario, la latencia, la integridad de los datos y la simplicidad operativa son factores determinantes.

El equipo de desarrollo está compuesto por **6 integrantes** y el proyecto se encuentra en etapa de **Producto Mínimo Viable (MVP)**. El criterio de arquitectura establece utilizar una estructura monolítica modular cuando el equipo de trabajo cuenta con menos de 15 personas, permitiendo concentrar el esfuerzo de desarrollo sin asumir la sobrecarga operativa y de infraestructura que requiere una arquitectura de microservicios.

---

## Decisión

Se decide adoptar el estilo arquitectónico **Monolito Modular Cloud-Native Containerizado** para el sistema MediTriage. 

Toda la aplicación se estructurará internamente mediante módulos delimitados con fronteras claras (triage, pacientes, validaciones), empaquetándose en una **única imagen de Docker** para su despliegue en servicios gestionados en la nube como **AWS ECS Fargate** o **GCP Cloud Run**.

---

## Razones de la decisión

1. **Eficiencia del Equipo:** Minimiza la fricción operacional y de despliegue, adecuándose a la capacidad actual de 6 desarrolladores durante la fase de MVP.
2. **Integridad de datos en urgencias:** La clasificación clínica exige transacciones ACID inmediatas sobre un único motor relacional (**PostgreSQL**), evitando la complejidad técnica de gestionar consistencia eventual o transacciones distribuidas (patrón Saga, etc.).
3. **Atributo de calidad (rendimiento):** Garantiza una latencia **p95 < 200**. La comunicación entre los módulos de triage, atención de pacientes y validaciones se ejecuta dentro de la memoria del mismo proceso, eliminando la latencia de red inherente a llamadas IPC/HTTP entre servicios.
4. **Despliegue y escalabilidad:** El empaquetamiento en contenedor permite un escalado horizontal automático en la nube sin requerir la administración manual de servidores o clústeres complejos.

---

## Alternativas descartadas

* Microservicios: Descartado debido a la sobrecarga operacional, complejidad de despliegue y costo de mantenimiento excesivo para un equipo reducido de 6 personas.
* Serverless puro (FaaS): Descartado por el riesgo de latencia introducido por los arranques en frío (*cold starts*), inaceptable en un contexto de emergencias médicas.

---

## Consecuencias

### Positivas
* Alta velocidad de desarrollo e integración durante la etapa de MVP.
* Latencia de comunicación entre módulos prácticamente nula (ejecución en memoria).
* Garantía de consistencia fuerte (ACID) en la base de datos PostgreSQL.
* Infraestructura simplificada mediante contenedores y servicios serverless de contenedores.

### Negativas
* Acoplamiento potencial: Requiere disciplina estricta en el código para respetar las fronteras entre módulos y evitar dependencias cíclicas.
* Escalado global del proceso: El escalado horizontal duplica toda la aplicación y no módulos individuales, lo cual es aceptable para la carga proyectada del MVP.
