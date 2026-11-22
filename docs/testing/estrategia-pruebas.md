# Estrategia general de pruebas – MediTriage

## 1. Objetivo

Definir una estrategia de pruebas para verificar la calidad, funcionalidad y confiabilidad de MediTriage, identificando qué componentes deben evaluarse mediante pruebas unitarias, de integración y End-to-End (E2E).

Se utilizará **pytest** como herramienta principal para las pruebas del backend desarrollado con FastAPI.

## 2. Tipos de pruebas

### 2.1. Pruebas unitarias

**Objetivo:** comprobar el funcionamiento individual de funciones, validaciones y componentes del backend, sin depender de servicios externos.

**Qué se probará:**
- Cálculo y validación del dígito verificador del RUT.
- Validación de los datos y esquemas de pacientes.
- Validación de signos vitales y datos del formulario de triage.
- Sanitización de información sensible.
- Formato y contenido de los registros de auditoría y logging.
- Validaciones de entradas y manejo de errores.

**Herramienta:** pytest.

**Criterio de aceptación:** las funciones deben entregar los resultados esperados, rechazar datos inválidos y ejecutar correctamente sus validaciones.

### 2.2. Pruebas de integración

**Objetivo:** comprobar que los distintos componentes del sistema funcionan correctamente al comunicarse entre sí.

**Qué se probará:**
- Integración de los endpoints de FastAPI con sus esquemas y validaciones.
- Comunicación del backend con PostgreSQL para registrar y consultar pacientes.
- Validación de restricciones de datos, como la unicidad del RUT.
- Registro y consulta de decisiones clínicas en PostgreSQL.
- Integración con Redis para la gestión de sesiones y estados temporales, cuando esté implementada.
- Comunicación con el servicio externo de inteligencia artificial para obtener recomendaciones de triage, cuando esté integrada.

**Herramientas:** pytest, HTTPX, FastAPI TestClient y PostgreSQL.

**Criterio de aceptación:** los componentes deben intercambiar información correctamente, procesar solicitudes válidas y responder adecuadamente ante errores.

Las pruebas que requieren servicios

### Pruebas BDD y datos sintéticos (`pytest-bdd`)

**Objetivo:** verificar flujos de negocio y contratos funcionales en lenguaje Gherkin apoyándose en datos sintéticos y aislamiento de base de datos.

- **Fábricas de datos sintéticos:** `backend/tests/factories.py` provee generadores reutilizables para pacientes, signos vitales según nivel ESI y roles de usuario.
- **Fixtures compartidas:** `backend/tests/bdd/conftest.py` entrega el cliente de pruebas de FastAPI (`client`), cabeceras de autenticación (`auth_headers`), conexión aislada a PostgreSQL con `rollback()` (`db_conn` y validación para no apuntar a producción) y datos sintéticos de signos vitales.
- **Patrón de referencia (`US-02`):** el equipo puede usar [`backend/tests/bdd/us02_decision_clinica.feature`](../../backend/tests/bdd/us02_decision_clinica.feature) y [`backend/tests/bdd/test_us02_decision_clinica.py`](../../backend/tests/bdd/test_us02_decision_clinica.py) como plantilla para nuevos escenarios BDD.

**Herramientas:** `pytest`, `pytest-bdd`, `FastAPI TestClient` y `psycopg`.
