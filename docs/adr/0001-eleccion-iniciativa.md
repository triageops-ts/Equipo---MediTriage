# ADR 0001 — Elección de iniciativa: MediTriage

## Fecha
17/08/2026

## Autores
Lucas Benítez, Kimberlly Guillén, Josefa Rodríguez, Marcela Contreras, Isidora Ramos y Antonia Moya

## Contexto y decisión

Los largos tiempos de espera en los servicios de emergencia constituyen un problema crítico para el sistema de salud. La elevada demanda provoca congestión y demoras en la evaluación y atención de los pacientes, especialmente de aquellos con condiciones graves que requieren atención inmediata, donde el tiempo de respuesta resulta vital.

Frente a esta problemática, el equipo decidió desarrollar MediTriage, una plataforma tecnológica diseñada para optimizar y agilizar el proceso de categorización clínica en los servicios de urgencia, reduciendo significativamente los tiempos de espera.

MediTriage examina en tiempo real los síntomas, la historia clínica y los signos vitales del paciente para generar, en menos de 3 segundos, una recomendación de priorización fundamentada en el índice ESI (1–5). De este modo, asiste al personal sanitario en la detección temprana de casos críticos. Asimismo, la plataforma incorpora estrictas medidas de seguridad como la anonimización de datos personales (PII), auditorías inmutables y control de acceso basado en roles, garantizando el pleno cumplimiento de la legislación chilena sobre protección de datos sensibles (Ley 19.628 y Ley 21.719).

## Alternativas descartadas

* **Mantener el triage manual, sin plataforma:** se descartó porque no resuelve el problema de fondo. La categorización seguiría dependiendo de la carga del personal en cada turno, sin una recomendación en menos de 3 s, sin trazabilidad de la decisión y sin auditoría inmutable de 5 años.
* **Sistema solo de reglas fijas (planilla o árbol de decisión sin IA):** se descartó como solución principal porque no interpreta el texto libre de los síntomas ni genera una justificación clínica en lenguaje natural. Sí se conserva como respaldo cuando la IA falla (ver IA-001).
* **Backend con un microservicio de inferencia separado (por ejemplo, un servicio de IA aparte del backend principal):** se descartó porque agrega saltos de red que ponen en riesgo la latencia menor a 3 s y más piezas que operar para un equipo pequeño. Con FastAPI en Python, la IA corre en el mismo proceso (ver también ADR 0002).

## Consecuencias positivas
* Cumplimiento Nativo de Baja Latencia (< 3 s): El uso de FastAPI junto con el motor asíncrono uvicorn/asyncio permite procesar la validación clínica, el desacople de PII y la llamada al modelo de lenguaje en paralelo, reduciendo los tiempos de respuesta del endpoint a milisegundos y cumpliendo con holgura el SLA de triage.

* Integración Fluida con el Ecosistema de Inteligencia Artificial: Al construir el backend en Python, se elimina la necesidad de microservicios intermediarios de inferencia; las librerías de orquestación (LangChain, LlamaIndex, DSPy) y los clientes de inferencia estructurada operan en el mismo proceso de ejecución.

* Blindaje de Datos Sensibles (Privacy by Design / Leyes 19.628 y 21.719): La combinación de esquemas tipados estrictos en Pydantic y las capacidades de PostgreSQL (pgcrypto y Row-Level Security) permite implementar una capa de sanitización y cifrado por columna antes de que cualquier dato salga hacia proveedores externos de IA.

* Actualización en Tiempo Real de la Sala de Espera: La arquitectura de frontend en Next.js con soporte de WebSockets/SSE permite que las reasignaciones y cambios dinámicos en la cola ESI se reflejen instantáneamente en las pantallas del personal médico y de enfermería, sin necesidad de recarga manual (polling innecesario).

* Integridad Transaccional y Auditoría Inmutable por 5 Años: El modelo relacional ACID de PostgreSQL garantiza la consistencia de los registros clínicos y facilita la creación de tablas de auditoría append-only preparadas para replicación en almacenamiento WORM (Write Once, Read Many).

* Mitigación Temprana de Errores Clínicos: La validación estricta de esquemas fisiológicos (rangos válidos de $SpO_2$, presión arterial, pulso y algoritmo Módulo 11 para el RUT chileno) ocurre en el borde de la API, evitando que datos corruptos o fuera de escala lleguen a la capa de inferencia o a la base de datos.

## Desafíos y Riesgos Mitigados

* Complejidad en la Gestión de Estado y Alta Disponibilidad (99.5%): Mantener actualizaciones en tiempo real mediante WebSockets o SSE en el frontend introduce el desafío de balancear tráfico persistente. Alcanzar el SLA del 99.5% mensual sin caídas diurnas requerirá un diseño de infraestructura tolerante a fallos, gestionando adecuadamente la reconexión de clientes y la replicación del estado ante posibles reinicios de los contenedores.

* Prevención de Fuga de Datos en la Capa de Observabilidad: Aunque la base de datos maneje el cifrado en reposo de la PII, el framework web y las herramientas de monitoreo registran trazas de las peticiones. Implementar middlewares robustos que enmascaren los datos sensibles de los pacientes en los logs de la aplicación es crítico para cumplir con la auditoría y respetar la normativa chilena de datos sensibles.

* Explicabilidad Determinista y Mitigación de Alucinaciones: El sistema no solo debe sugerir una categoría ESI (1–5), sino que debe justificar la priorización. El reto radica en diseñar flujos de IA con salvaguardas (guardrails) que fuercen respuestas deterministas y clínicamente válidas, evitando alucinaciones del modelo para asegurar que el registro inmutable de 5 años sea auditable y confiable.

* Seguridad Ofensiva en el Borde (Prompt Injection): Al procesar texto libre proveniente del formulario de síntomas, la validación de esquemas tipados no es suficiente para prevenir ataques semánticos. Será obligatorio implementar filtros DevSecOps que saniticen los prompts y eviten que un usuario manipule el modelo de lenguaje para alterar artificialmente su nivel de urgencia.






