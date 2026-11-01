# 🏥 API Base - MediTriage (Contrato V1)

Este documento define los endpoints principales RESTful, filtros, paginación y códigos de estado esperados para el MVP. Sirve como contrato para el desarrollo en paralelo de Frontend y Backend.

---

## ⚙️ Estándares Generales de la API

*   **Paginación por defecto:** Se usará el formato `?skip=0&limit=20` en los endpoints que devuelvan listas.
*   **Códigos de Estado (HTTP Status Codes) Estándar:**
    *   `200 OK`: Petición exitosa.
    *   `201 Created`: Recurso creado exitosamente.
    *   `400 Bad Request`: Error en los datos enviados por el cliente.
    *   `401 Unauthorized`: Falta token de autenticación.
    *   `403 Forbidden`: El usuario no tiene permisos (ej. rol insuficiente).
    *   `404 Not Found`: El recurso solicitado no existe.
    *   `409 Conflict`: Conflicto de estado (ej. paciente ya registrado).
    *   `422 Unprocessable Entity`: Error de validación de datos (petición mal formada).
    *   `500 Internal Server Error`: Error inesperado en el servidor/IA.

---

## 👥 1. Dominio: Pacientes (Admisión / Sala de Espera)

| Método | Endpoint | Descripción | Códigos Esperados | Paginación / Filtros |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/patients` | Registra un nuevo paciente (RUT, nombre, consentimiento). | `201`, `400`, `409` | N/A |
| **GET** | `/patients` | Obtiene la lista de pacientes registrados. | `200` | **Pag:** Sí (`skip`, `limit`) <br> **Filtros:** `?rut={rut}`, `?name={nombre}` |

---

## 🩺 2. Dominio: Triages (Enfermería y Médico)

| Método | Endpoint | Descripción | Códigos Esperados | Paginación / Filtros |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/triages` | Crea evaluación de triage. Recibe síntomas; retorna IA ESI. | `201`, `422` | N/A |
| **GET** | `/triages` | Lista de triages activos (para Tablero Médico). | `200` | **Pag:** Sí (`skip`, `limit`) <br> **Filtros:** `?status={waiting\|attending\|discharged}`, `?esi_level={1-5}`, `?sort=-esi_level` |
| **PATCH**| `/triages/{triage_id}`| Actualiza el estado de flujo del paciente (Ej: "En Atención"). | `200`, `404`, `422` | N/A |
| **POST** | `/triages/{triage_id}/overrides` | Sobrescribe nivel ESI de IA. Requiere justificación. | `201`, `400`, `404` | N/A |

---

## 📋 3. Dominio: Auditoría y Trazabilidad

| Método | Endpoint | Descripción | Códigos Esperados | Paginación / Filtros |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/audit-logs` | Historial inmutable para Auditoría (Discrepancias). | `200`, `403` | **Pag:** Sí (`skip`, `limit`) <br> **Filtros:** `?start_date={fecha}&end_date={fecha}`, `?has_discrepancy=true`, `?user_id={id}` |

---
*Nota para el equipo: Estos endpoints están en desarrollo. Las estructuras exactas de los JSON (requests/responses) se definirán en la especificación OpenAPI (Swagger) generada por FastAPI.*
