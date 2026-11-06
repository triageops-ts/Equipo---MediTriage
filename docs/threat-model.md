# Modelo de Amenazas STRIDE — Módulo de Triage y Decisión Clínica

## 1. Selección del Componente
Para el presente análisis se ha seleccionado únicamente el **Módulo de Triage y Decisión Clínica**. Este componente se ubica en el backend del sistema (`backend/app/api/v1/triage.py`) desarrollado en Python/FastAPI. Es responsable de la recepción de formularios clínicos (signos vitales y síntomas) y del registro de la decisión médica final sobre el nivel ESI.

---

## 2. Descripción del Componente y Flujo de Datos
Con base en la implementación real de `triage.py` y los esquemas de base de datos:

* **Origen y Cliente Interactivo:** El cliente web y móvil (Frontend) consume los endpoints `/triage/formulario` y `/triage/{episodio_id}/decision` enviando peticiones HTTPS autenticadas.
* **Datos de Entrada:** 
  * Identificador del paciente (`patient_id`), identificador del operador (`usuario_id`), signos vitales, listado de síntomas y motivo de consulta en texto libre (`motivo_consulta`).
  * En la decisión final: el nivel ESI seleccionado (`nivel_esi_final`) y la justificación requerida si difiere de la sugerencia de la IA.
* **Procesamiento Interno:** 
  * Sanitización automática del motivo de consulta en texto libre mediante la función `sanitize_symptoms_text()`.
  * Control de concurrencia mediante bloqueo de registros (`SELECT ... FOR UPDATE`) sobre la tabla `episodio_triage` durante la toma de decisiones.
  * Comparación de coincidencia entre la decisión médica final y el nivel ESI sugerido previamente por el modelo de IA (`clasificacion_ia`).
* **Almacenamiento y Persistencia:** 
  * Inserción en las tablas PostgreSQL `episodio_triage`, `signos_vitales`, `sintomas_triage` y `decision_clinica` dentro de transacciones atómicas de `psycopg`.
  * Cifrado de datos sensibles en reposo mediante la extensión `pgcrypto`.
  * Registro inmutable de fechas/horas directas desde la base de datos en UTC (`now() AT TIME ZONE 'UTC'`).

---

## 3. Matriz de Mitigaciones STRIDE

| Categoría STRIDE | Amenaza | Mitigación Implementada / Control que la Cubre | Estado |
|---|---|---|---|
| **Spoofing** | Creación de registros de triage o decisiones por usuarios no autenticados. | Validación obligatoria de `usuario_id` existente (`_EXISTE_USUARIO`) y autenticación de endpoints. | Existente |
| **Tampering** | Inyección SQL a través del texto libre del motivo de consulta o parámetros. | Consultas SQL parametrizadas con `psycopg` y sanitización con `sanitize_symptoms_text()`. | Existente |
| **Repudiation** | Modificación o sobrescritura maliciosa de decisiones clínicas ya registradas. | Control de duplicados (`_YA_TIENE_DECISION`), sellado temporal en UTC e inmutabilidad de registros. | Existente |
| **Divulgación de Información** | Filtración de datos de salud (PII / PHI) en logs o respuestas del servidor. | Sanitización previa de texto libre, enmascaramiento de datos y cifrado en reposo con `pgcrypto`. | Existente |
| **Denial of Service** | Ataques de condición de carrera (*Race Conditions*) en decisiones simultáneas. | Bloqueo a nivel de fila con `SELECT ... FOR UPDATE` (`_BLOQUEAR_EPISODIO`) en transacciones aisladas. | Existente |
| **Elevation of Privilege** | Un operador altera la recomendación de la IA sin dejar rastro ni justificación. | Exigencia de justificación (`JUSTIFICACION_MIN_CARACTERES`) y trazabilidad de discrepancias (`coincide_con_ia`). | Existente |

---

## 4. Aprovechamiento de Controles Existentes y Brechas (Controles que Faltan)

* **Zero PII y Sanitización de Datos:** Se implementa de manera activa mediante funciones de limpieza de texto libre (`sanitize_symptoms_text`) en el núcleo del backend para evitar el almacenamiento de información personal identificable innecesaria.
* **Cifrado en Reposo:** Soportado mediante la extensión criptográfica `pgcrypto` en la base de datos PostgreSQL.
* **Aislamiento y Seguridad (RLS):** Se emplean políticas de seguridad a nivel de fila (*Row Level Security*) para restringir el acceso a los datos clínicos exclusivamente a usuarios autorizados.
* **Trazabilidad e Inmutabilidad (*Audit Log*):** Se mantiene un registro de auditoría con marcas de tiempo sincronizadas en UTC y hashes encadenados para garantizar la integridad de las acciones médicas.
* **Controles Pendientes / Brechas:** 
  * Para el alcance específico de este módulo (`triage.py`), **no faltan controles críticos**. Todas las mitigaciones de la matriz STRIDE se encuentran operativas e integradas en la lógica del negocio. Como mejora futura o propuesta a nivel de arquitectura general, se podría evaluar la implementación de un cifrado de extremo a extremo adicional en la capa de transporte para clientes móviles nativos fuera de la red local.

---

## 5. Relación de Mitigaciones con el Pipeline de DevSecOps

Para asegurar que las defensas del Módulo de Triage no sufran regresiones, cada control se verifica de manera automatizada en el pipeline de Integración Continua (CI):

* **SAST (Static Application Security Testing):**
  * *Relación con Mitigaciones:* Verifica el uso correcto y sin excepciones de las consultas parametrizadas en `psycopg` para evitar vulnerabilidades de inyección SQL (Tampering). Analiza también la correcta implementación de las validaciones de esquemas y el bloqueo de registros por concurrencia (`FOR UPDATE`).
* **SCA (Software Composition Analysis):**
  * *Relación con Mitigaciones:* Escanea continuamente las dependencias y librerías externas declaradas (como FastAPI, `psycopg` y los requerimientos exactos en `requirements.txt`) para asegurar que no existan vulnerabilidades conocidas en componentes de terceros que puedan comprometer la autenticación (Spoofing) o la confidencialidad de los datos de salud (Information Disclosure).
* **Secret Scanning (Escaneo de Secretos):**
  * *Relación con Mitigaciones:* Detecta de forma automática en los commits y archivos de configuración la exposición accidental de credenciales de base de datos, llaves de API o tokens JWT, evitando accesos no autorizados al backend y garantizando la protección frente a la suplantación de identidad.
