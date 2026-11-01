# Checklist de los 12 Factores

| # | Factor | Estado | Acción Concreta | Responsable |
|---|---|---|---|---|
| *01 Codebase* | Repositorios de código | Cumple | Verificar que cada microservicio mantenga un repositorio de Git totalmente independiente y asegurar que no exista código duplicado o copiado manualmente entre diferentes servicios. | Lucas Benítez (Jefe técnico) |
| *02 Dependencies* | Declaración y aislamiento | Cumple | Validar que todos los archivos de definición de dependencias estén completos y bloqueados (ej. `package-lock.json`, `poetry.lock`), garantizando que la aplicación no dependa de librerías preinstaladas en el sistema operativo. | Isidora Ramos (DevSecOps) y Lucas Benítez (Jefe técnico) |
| *03 Config* | Variables de entorno | Cumple | Inyección de configuración mediante variables de entorno consumidas por Pydantic Settings (`DATABASE_URL`, credenciales y entorno). Ningún secreto se expone en el repositorio Git. |Lucas Benítez (Jefe técnico) |
| *04 Backing services* | Recursos adjuntos (DB) | Cumple | La base de datos (PostgreSQL) se trata como un recurso adjunto e intercambiable a través de la variable `DATABASE_URL`. El backend se conecta sin requerir cambios de código entre local y nube. | Isidora Ramos (DevSecOps) |
| *05 Build, release , run* | Separación de etapas | No cumple | Configurar pipeline en GitHub Actions que compile la imagen Docker (Build), genere el tag de versión (Release) y despliegue en el entorno de ejecución (Run) de forma automatizada. | Isidora Ramos (DevSecOps) |
| *05 Build, release, run* | Identificadores únicos | No cumple | Etiquetar cada artifact con el commit SHA de Git en el pipeline de CI/CD. | Isidora Ramos (DevSecOps) |
| *05 Build, release, run* | Inmutabilidad en ejecución | Cumple | Prohibir modificar código en tiempo de ejecución. | - |
| *06 Processes* | Procesos stateless | Cumple | Mantener la API en FastAPI sin almacenamiento de estado en memoria local y delegar la persistencia a PostgreSQL, validando en pruebas de carga. | Lucas Benítez (Tech Lead) / Marcela & Josefa (QA) |
| *06 Processes* | Aislamiento de memoria en IA | No cumple | Asegurar que el modelo de triaje procese los síntomas sin guardar historial de pacientes en la memoria local (RAM). | Antonia Moya (AI/Data Lead) |
| *07 Port binding* | Vinculación autónoma | No cumple | Modificar la configuración de Uvicorn y el archivo `docker-compose.yml` para exponer el puerto a través de la variable de entorno `$PORT`. | Isidora Ramos (DevSecOps) |
| *07 Port binding*| Inyección de puertos | Cumple | Inyección de puertos mediante variables de entorno. | - |
| *08 Concurrency* | Escalado por procesos | No cumple | Definir Uvicorn con múltiples workers y N réplicas del contenedor Backend detrás de un load balancer (ECS Fargate + ALB). | Isidora Ramos (DevSecOps) |
| *08 Concurrency* | Backend sin estado | Cumple | Las sesiones y el estado en vivo ya viven en Redis, no en memoria del proceso (ver C4 L2). | Lucas Benítez (Jefe técnico) |
| *08 Concurrency* | Reparto de carga | No cumple | Definir un load balancer (ALB o equivalente) delante de las réplicas del Backend, con health checks configurados. | Isidora Ramos (DevSecOps) |
| *09 Disposability* | Manejo de SIGTERM | No cumple | Implementar un `lifespan handler` en FastAPI que, al recibir SIGTERM, deje de aceptar conexiones nuevas y drene las conexiones activas antes de cerrar. | Isidora Ramos (DevSecOps) |
| *09 Disposability* | Cierre ordenado | No cumple | Cerrar de forma ordenada conexiones WebSocket/SSE, Redis y PostgreSQL, esperando solicitudes en curso con un timeout. | Isidora Ramos (DevSecOps) |
| *09 Disposability* | Apagado verificable | No cumple | Agregar verificación en CI/CD que mida el tiempo entre el envío de SIGTERM y el cierre completo del contenedor (< 30 s). | Isidora Ramos (DevSecOps) |
| *10 Dev/prod parity* | Versiones idénticas | No cumple | Levantar `docker-compose.yml` con las mismas versiones de PostgreSQL y Redis que en producción, con `pgcrypto` habilitado. | Isidora Ramos (DevSecOps) |
| *10 Dev/prod parity* | Sin mocks locales | No cumple | Prohibir mocks o librerías en memoria para Postgres/Redis en desarrollo; todo el equipo debe correr contra instancias reales del docker-compose. | Lucas Benítez (Jefe técnico) |
| *10 Dev/prod parity* | Paridad de configuración | No aplica | Cubierto por el Factor 03 (Config). | - |
| *11 Logs* | Logs a stdout/stderr | No cumple | Configurar backend (FastAPI/Uvicorn) y frontend (Next.js) para loggear en JSON estructurado a stdout, prohibiendo escritura a disco. | Isidora Ramos (DevSecOps) |
| *11 Logs* | Agregación de logs | No cumple | Agregar al C4 L2 un sistema externo tipo Loki + Grafana o CloudWatch Logs, y definirlo en el ADR. | Isidora Ramos (DevSecOps) |
| *11 Logs* | PII enmascarada | No cumple | Implementar middleware de sanitización de logs, separado del audit log en Postgres. | Lucas Benítez (Jefe técnico) |
| *11 Logs* | Audit Log separado | Cumple | Registro de negocio separado del log técnico en Postgres. | - |
| *12 Admin Processes* | Herramienta de migraciones | No cumple | Adoptar Alembic, versionado en el mismo repositorio que el backend. | Lucas Benítez (Jefe técnico) |
| *12 Admin Processes* | Migraciones en release | No cumple | Definir un job en CI/CD que corra `alembic upgrade head` usando la imagen Docker del backend. | Isidora Ramos (DevSecOps) |
| *12 Admin Processes* | Tareas admin puntuales | No cumple | Crear comandos CLI dentro del backend (ej. `python -m app.cli seed-roles`) invocables como contenedor one-off. | Lucas Benítez (Jefe técnico) |
| *12 Admin Processes* | Representación en C4 / ADR | No cumple | Agregar nota o componente en el diagrama C4 L2 / ADR. | - |
