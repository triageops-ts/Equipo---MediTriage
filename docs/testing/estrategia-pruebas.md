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
- Integración con Redis para la gestión de sesiones y estados temporales, cuando esté implementada.
- Comunicación con el servicio externo de inteligencia artificial para obtener recomendaciones de triage, cuando esté integrada.

**Herramientas:** pytest, HTTPX y FastAPI TestClient.

**Criterio de aceptación:** los componentes deben intercambiar información correctamente, procesar solicitudes válidas y responder adecuadamente ante errores.

Las pruebas que requieren servicios externos deben ejecutarse con las dependencias configuradas y disponibles.

### 2.3. Pruebas End-to-End (E2E)

**Objetivo:** verificar el funcionamiento del sistema completo desde la perspectiva del usuario.

**Flujo que se probará:**
1. Ingreso de los datos del paciente.
2. Registro de signos vitales y síntomas.
3. Envío del formulario de triage.
4. Procesamiento de la solicitud por el backend.
5. Obtención de la recomendación de priorización y su justificación.
6. Visualización del resultado en la interfaz.
7. Manejo de errores durante el proceso.

**Herramienta:** se evaluará Playwright para automatizar los flujos de usuario cuando el frontend y el backend estén integrados.

**Criterio de aceptación:** el usuario debe poder completar el flujo de triage y recibir el resultado esperado sin errores que interrumpan el proceso.

## 3. Configuración del entorno de pruebas

El backend utiliza Python 3.11 y pytest.

Las dependencias de pruebas se encuentran declaradas en `backend/requirements.txt`:

- `pytest`: ejecución de pruebas.
- `pytest-cov`: medición de cobertura.
- `httpx`: pruebas de solicitudes HTTP.

Para instalar las dependencias:

```bash
python -m pip install -r requirements.txt
```

Para ejecutar las pruebas desde la carpeta `backend`:

```bash
python -m pytest -v
```

Para visualizar también los motivos de las pruebas omitidas:

```bash
python -m pytest -v -rs
```

Para medir la cobertura:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

## 4. Criterios generales de calidad

- Todas las pruebas deben ejecutarse sin errores.
- Los datos utilizados deben ser ficticios y no contener información real de pacientes.
- Las validaciones deben contemplar datos correctos e incorrectos.
- Las pruebas de integración deben considerar las dependencias externas necesarias.
- Los errores deben manejarse de manera controlada.
- Los resultados de las ejecuciones deben quedar registrados como evidencia.

## 5. Estado actual de las pruebas

Se realizó una ejecución de las pruebas automatizadas del backend mediante pytest.

**Fecha de ejecución:** 2 de noviembre de 2026.

**Entorno utilizado:**
- Python 3.11.9.
- pytest 9.2.0.
- pytest-cov 7.1.0.

**Comando ejecutado:**

```bash
python -m pytest -v -rs
```

**Resultado obtenido:**

| Resultado | Cantidad |
|---|---:|
| Pruebas aprobadas | 93 |
| Pruebas omitidas (SKIPPED) | 3 |
| Pruebas fallidas | 0 |
| Total | 96 |

Las 93 pruebas aprobadas verifican funcionalidades relacionadas con la salud del servicio, logging, validación de pacientes, RUT, sanitización y esquemas de triage.

Las 3 pruebas omitidas pertenecen a `tests/test_patients_db.py`. Estas requieren las variables de entorno `DATABASE_URL` y `APP_ENCRYPTION_KEY` para conectarse a PostgreSQL y utilizar el mecanismo de cifrado.

Por este motivo, las pruebas de integración con PostgreSQL aún no se consideran validadas.

**Conclusión de la ejecución:** pytest finalizó correctamente, con 93 pruebas aprobadas, 3 omitidas y ninguna fallida.

## 6. Trabajo pendiente

- Configurar las variables de entorno necesarias para ejecutar las pruebas de integración con PostgreSQL.
- Ejecutar y verificar las pruebas de integración con Redis cuando corresponda.
- Incorporar pruebas de integración para el servicio de inteligencia artificial.
- Implementar pruebas E2E cuando el flujo completo entre frontend y backend esté disponible.
- Revisar los resultados de cobertura y ampliar las pruebas donde sea necesario.

## 7. Conclusión

MediTriage cuenta con una base de pruebas automatizadas para el backend utilizando pytest. La ejecución inicial obtuvo 93 pruebas aprobadas, 3 omitidas por falta de configuración de dependencias y ninguna prueba fallida.

Esta estrategia establece los criterios para continuar validando el sistema mediante pruebas unitarias, de integración y End-to-End, a medida que se completen sus componentes e integraciones.


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
- Integración con Redis para la gestión de sesiones y estados temporales, cuando esté implementada.
- Comunicación con el servicio externo de inteligencia artificial para obtener recomendaciones de triage, cuando esté integrada.

**Herramientas:** pytest, HTTPX y FastAPI TestClient.

**Criterio de aceptación:** los componentes deben intercambiar información correctamente, procesar solicitudes válidas y responder adecuadamente ante errores.

Las pruebas que requieren servicios externos deben ejecutarse con las dependencias configuradas y disponibles.

### 2.3. Pruebas End-to-End (E2E)

**Objetivo:** verificar el funcionamiento del sistema completo desde la perspectiva del usuario.

**Flujo que se probará:**
1. Ingreso de los datos del paciente.
2. Registro de signos vitales y síntomas.
3. Envío del formulario de triage.
4. Procesamiento de la solicitud por el backend.
5. Obtención de la recomendación de priorización y su justificación.
6. Visualización del resultado en la interfaz.
7. Manejo de errores durante el proceso.

**Herramienta:** se evaluará Playwright para automatizar los flujos de usuario cuando el frontend y el backend estén integrados.

**Criterio de aceptación:** el usuario debe poder completar el flujo de triage y recibir el resultado esperado sin errores que interrumpan el proceso.

## 3. Configuración del entorno de pruebas

El backend utiliza Python 3.11 y pytest.

Las dependencias de pruebas se encuentran declaradas en `backend/requirements.txt`:

- `pytest`: ejecución de pruebas.
- `pytest-cov`: medición de cobertura.
- `httpx`: pruebas de solicitudes HTTP.

Para instalar las dependencias:

```bash
python -m pip install -r requirements.txt
```

Para ejecutar las pruebas desde la carpeta `backend`:

```bash
python -m pytest -v
```

Para visualizar también los motivos de las pruebas omitidas:

```bash
python -m pytest -v -rs
```

Para medir la cobertura:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

## 4. Criterios generales de calidad

- Todas las pruebas deben ejecutarse sin errores.
- Los datos utilizados deben ser ficticios y no contener información real de pacientes.
- Las validaciones deben contemplar datos correctos e incorrectos.
- Las pruebas de integración deben considerar las dependencias externas necesarias.
- Los errores deben manejarse de manera controlada.
- Los resultados de las ejecuciones deben quedar registrados como evidencia.

## 5. Estado actual de las pruebas

Se realizó una ejecución de las pruebas automatizadas del backend mediante pytest.

**Fecha de ejecución:** 2 de noviembre de 2026.

**Entorno utilizado:**
- Python 3.11.9.
- pytest 9.2.0.
- pytest-cov 7.1.0.

**Comando ejecutado:**

```bash
python -m pytest -v -rs
```

**Resultado obtenido:**

| Resultado | Cantidad |
|---|---:|
| Pruebas aprobadas | 93 |
| Pruebas omitidas (SKIPPED) | 3 |
| Pruebas fallidas | 0 |
| Total | 96 |

Las 93 pruebas aprobadas verifican funcionalidades relacionadas con la salud del servicio, logging, validación de pacientes, RUT, sanitización y esquemas de triage.

Las 3 pruebas omitidas pertenecen a `tests/test_patients_db.py`. Estas requieren las variables de entorno `DATABASE_URL` y `APP_ENCRYPTION_KEY` para conectarse a PostgreSQL y utilizar el mecanismo de cifrado.

Por este motivo, las pruebas de integración con PostgreSQL aún no se consideran validadas.

**Conclusión de la ejecución:** pytest finalizó correctamente, con 93 pruebas aprobadas, 3 omitidas y ninguna fallida.

## 6. Trabajo pendiente

- Configurar las variables de entorno necesarias para ejecutar las pruebas de integración con PostgreSQL.
- Ejecutar y verificar las pruebas de integración con Redis cuando corresponda.
- Incorporar pruebas de integración para el servicio de inteligencia artificial.
- Implementar pruebas E2E cuando el flujo completo entre frontend y backend esté disponible.
- Revisar los resultados de cobertura y ampliar las pruebas donde sea necesario.

## 7. Conclusión

MediTriage cuenta con una base de pruebas automatizadas para el backend utilizando pytest. La ejecución inicial obtuvo 93 pruebas aprobadas, 3 omitidas por falta de configuración de dependencias y ninguna prueba fallida.

Esta estrategia establece los criterios para continuar validando el sistema mediante pruebas unitarias, de integración y End-to-End, a medida que se completen sus componentes e integraciones.
