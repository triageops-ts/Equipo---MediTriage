# ADR 0004: Selección de Motores de Persistencia, Broker de Eventos y Patrón Outbox

## Fecha
08/10/2026

## Autores
Josefa Rodriguez, Lucas Benítez, Marcela Contreras, Isidora Ramos, Antonia Moya y Kimberlly Guillén

---
## Contexto

El sistema MediTriage se encuentra en etapa de MVP con un equipo de desarrollo de 6 integrantes, operando bajo un monolito modular cloud-native (según el ADR 0003). En este escenario, es necesario definir la estrategia de persistencia de datos por contexto delimitado (*Bounded Context*), la mensajería asíncrona mediante un broker de eventos, el manejo del patrón Outbox y un mecanismo de resiliencia ante tiempos de espera excesivos o fallas en los servicios externos de Inteligencia Artificial.

Los requerimientos clave a resolver son:
1. **Garantías transaccionales y legales:** Integridad estricta y transacciones ACID inmediatas en la clasificación clínica y admisión, cumpliendo con las Leyes 19.628 y 21.719 de protección de datos sensibles (cifrado en reposo con `pgcrypto`, Row-Level Security y un *Audit Log* inmutable por 5 años sin PII).
2. **Tiempo real y notificaciones:** Actualización fluida del Tablero de Espera en el frontend.
3. **Resiliencia ante fallas de IA:** Mantener un SLA estricto limitando las llamadas a la IA a 1500 ms, activando un *fallback* heurístico automático si se supera el tiempo límite.
4. **Consistencia de eventos:** Garantizar el transporte seguro de eventos de dominio internos sin pérdida de información entre PostgreSQL y el broker.

---

## Decisión

Se han tomado las siguientes decisiones arquitectónicas:

1. **Persistencia Principal por Contexto Delimitado:**
   - **Admisión y Registro de Pacientes:** Utiliza **PostgreSQL** para integridad referencial estricta y modelo relacional, sin broker (API REST).
   - **Triage y Clínica (Core Domain):** Utiliza **PostgreSQL** para transacciones ACID inmediatas y **Redis Streams / Pub/Sub** como broker.
   - **Inferencia y Soporte de IA:** Utiliza **PostgreSQL** para guardar tokens efímeros y latencias, complementado con caché en Redis para heurísticas de *fallback*.
   - **Auditoría y Gobernanza:** Centraliza el *Audit Log* en **PostgreSQL** mediante RLS y tablas de solo-inserción con encadenamiento criptográfico, consumiendo eventos de Redis Streams.

2. **Gestión de Eventos y Broker:**
   - **Redis Pub/Sub:** Se conserva exclusivamente de forma efímera para los avisos en vivo orientados a la interfaz visual del Tablero de Espera.
   - **Redis Streams:** Se adopta como el broker de dominio para el transporte seguro de eventos y la implementación del Patrón Outbox, asegurando persistencia en disco y retención de mensajes si un consumidor está inactivo, reutilizando la infraestructura existente sin sumar costos.
   - **Patrón Outbox:** El servicio guarda el dato de negocio y el evento en PostgreSQL dentro de una misma transacción atómica. Un proceso publicador lee la tabla *outbox* y los envía a Redis Streams, mientras que los consumidores implementan idempotencia ignorando duplicados por medio del `event_id`.

3. **Flujo de Timeout y Fallback de la IA:**
   - El módulo de Triage solicita la clasificación a la IA con un límite de tiempo estricto de **1500 ms**.
   - Si la IA no responde a tiempo, se activa el *fallback* mediante reglas heurísticas locales. La base de datos registra la clasificación indicando explícitamente el origen a través del campo `modelo_usado`.

---

## Razones de la decisión

1. **Cumplimiento legal y seguridad clínica:** PostgreSQL garantiza transacciones ACID inmediatas y soporta controles avanzados (RLS, cifrado y *Audit Log* inmutable con hashes) exigidos por la normativa de datos sensibles, evitando la complejidad de la consistencia eventual.
2. **Eficiencia operativa del equipo:** Reutilizar el clúster de Redis existente mediante *Streams* y *Pub/Sub* permite cubrir las necesidades de mensajería en tiempo real y persistencia de eventos sin añadir la curva de aprendizaje de herramientas externas, adaptándose perfectamente a un equipo de 6 desarrolladores.
3. **Resiliencia y trazabilidad:** El flujo de *timeout* (1500 ms) con *fallback* heurístico y el registro detallado en el campo `modelo_usado` aseguran el cumplimiento del SLA clínico, manteniendo la trazabilidad completa que posteriormente viaja hacia Auditoría mediante el patrón Outbox.

---

## Alternativas descartadas

- **MongoDB y Cassandra (Persistencia):** Descartados. MongoDB no aporta ventajas al no requerir modelos *schemaless* y complica el cumplimiento normativo; Cassandra está orientada a escrituras masivas distribuidas y añade una complejidad innecesaria para un hospital local.
- **Pinecone (BD Vectorial) y EventStoreDB:** Descartados. MediTriage no realiza búsquedas semánticas sobre historiales clínicos (solo envía vectores estructurados), y el volumen de eventos del MVP no justifica la complejidad de un motor puro de *Event Sourcing*.
- **RabbitMQ y Amazon SQS/SNS (Broker):** Descartados. RabbitMQ introduce una sobrecarga operativa y administrativa excesiva para un equipo pequeño, y SQS/SNS genera latencias de red externas innecesarias para los eventos internos del monolito.
- **CORS y Saga Compleja:** Descartados, ya que la arquitectura se sustenta en un monolito modular con una sola base de datos relacional y transacciones ACID, evitando orquestaciones y compensaciones innecesarias.

---

## Consecuencias

### Positivas
- Garantía absoluta de consistencia transaccional (ACID) y cumplimiento legal estricto en el almacenamiento clínico.
- Arquitectura de mensajería robusta y resiliente ante caídas de consumidores gracias a la persistencia en disco de Redis Streams.
- Alta disponibilidad y resiliencia en el proceso crítico de Triage ante fallas o latencias de la API de IA externa.
- Simplicidad operativa al no introducir nuevos motores de bases de datos ni brokers externos complejos para el equipo.

### Negativas
- Mayor disciplina requerida en el equipo de desarrollo para asegurar la implementación correcta de la idempotencia en los consumidores mediante el uso estricto del `event_id`.
- Dependencia del clúster de Redis tanto para las notificaciones en tiempo real del frontend como para el transporte de eventos de dominio a través de Streams.
