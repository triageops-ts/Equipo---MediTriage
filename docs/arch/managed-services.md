# Selección de Servicios Gestionados (Managed Services)

En alineación con el Diagrama C4 Nivel 2 del proyecto MediTriage, se identifican y seleccionan los siguientes servicios gestionados para cada contenedor del sistema:

| Contenedor (C4 L2) | Servicio Gestionado Elegido | Criterio / Justificación Técnica |
| :--- | :--- | :--- |
| **Frontend** | **Vercel** | Hosting Serverless optimizado para Next.js y React. Ofrece CDN global, despliegues automáticos vía CI/CD y gestión de WebSockets/SSE para las 4 vistas por rol. |
| **Backend API** | **Render (PaaS)** | Plataforma gestionada para contenedores Docker con FastAPI/Python 3.11+. Facilita la inyección de variables de entorno, escalado horizontal y conexión segura TLS. |
| **Base de Datos** | **Supabase / AWS RDS (PostgreSQL)** | PostgreSQL gestionado con soporte nativo para la extensión `pgcrypto` y políticas Row-Level Security (RLS) para proteger los datos médicos de los pacientes. |
| **Caché / Mensajería** | **Upstash Redis / Redis Cloud** | Instancia gestionada de Redis optimizada para Pub/Sub y manejo de sesiones en tiempo real, garantizando la emisión de actualizaciones en vivo vía WSS. |

## Criterios Integrados
* **Inferencia IA:** La orquestación corre en el Backend mediante LangChain hacia la API externa de Anthropic (Claude 3 Haiku).
* **Seguridad:** Conexiones cifradas hacia PostgreSQL mediante SSL/TLS (`sslmode=require`).
