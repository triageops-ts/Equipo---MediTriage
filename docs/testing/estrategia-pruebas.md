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
