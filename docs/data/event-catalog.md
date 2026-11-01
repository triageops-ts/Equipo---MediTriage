# Catálogo de Eventos - MediTriage

Catálogo de eventos de dominio para la arquitectura orientada a eventos de MediTriage. Define el ciclo de vida principal, productores, consumidores, esquemas JSON y transmisión en tiempo real sin PII.

---

## Resumen del Catálogo de Eventos

| Evento | Versión | Contexto Productor | Contextos Consumidores | Notificación Tiempo Real (WS/SSE) |
| :--- | :---: | :--- | :--- | :---: |
| `paciente.registro.completado` | v1.0 | Admisión y Registro de Pacientes | Triage y Decisión Clínica, Auditoría y Gobernanza | Sí (Actualiza sala) |
| `paciente.constantes_vitales.ingresadas` | v1.0 | Triage y Decisión Clínica | Contexto de Inferencia y Soporte de IA | No (Evento interno) |
| `triage.evaluacion.iniciada` | v1.0 | Triage y Decisión Clínica | Inferencia y Soporte de IA, Auditoría y Gobernanza | Sí (Estado en espera) |
| `ia.clasificacion.solicitada` | v1.0 | Triage y Decisión Clínica | Inferencia y Soporte de IA | No (Interno asíncrono) |
| `ia.clasificacion.sugerida` | v1.0 | Inferencia y Soporte de IA | Triage y Decisión Clínica, Auditoría y Gobernanza | Sí (Sugerencia ESI) |
| `triage.clasificacion.respaldo_aplicada` | v1.0 | Triage y Decisión Clínica | Auditoría y Gobernanza | Sí (Alerta de Fallback) |
| `triage.evaluacion.confirmada` | v1.0 | Triage y Decisión Clínica | Admisión y Registro, Auditoría y Gobernanza | Sí (Asignación de espera) |
| `triage.override.ejecutado` | v1.0 | Triage y Decisión Clínica | Auditoría y Gobernanza | Sí (Cambio prioritario) |
| `paciente.atencion.iniciada` | v1.0 | Triage y Decisión Clínica | Admisión y Registro, Auditoría y Gobernanza | Sí (Llamado a box) |
| `notificacion.alerta.disparada` | v1.0 | Triage y Decisión Clínica | Tablero Frontend (WS) | Sí (Alerta crítica) |
| `audit.registro.creado` | v1.0 | Auditoría y Gobernanza | Almacenamiento Seguro | No (Persistencia) |
| `paciente.alta.registrada` | v1.0 | Admisión y Registro de Pacientes | Triage y Decisión Clínica | Sí (Cierre de ciclo) |

---
## Detalle y Esquema de Eventos (JSON Schemas - Zero PII)

### 1. paciente.registro.completado

- **Descripción:** Se emite cuando un paciente completa el proceso de admisión e inicia un episodio de triage.

- **Productor:** Contexto de Admisión y Registro de Pacientes

- **Consumidores:** Contexto de Triage y Decisión Clínica, Contexto de Auditoría y Gobernanza Médico-Legal

- **Tiempo Real (WS/SSE):** Sí (Notifica nueva entrada en la lista de espera).

```json
{
  "event_id": "evt_101a2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:00:00Z",
  "producer": "admision-service",
  "data": {
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "token_correlacion_efimero": "tok_sec_abc123",
    "fecha_hora_evento": "2026-10-06T19:58:00Z",
    "estado": "en_espera"
  }
}
```

---

### 2. paciente.constantes_vitales.ingresadas

- **Descripción:** Registro de constantes fisiológicas objetivas (presión arterial, FC, SpO2, temperatura) asociadas al episodio.
- **Productor:** Contexto de Triage y Decisión Clínica
- **Consumidores:** Contexto de Inferencia y Soporte de IA
- **Tiempo Real (WS/SSE):** No (Evento interno de traspaso de datos).

```json
{
  "event_id": "evt_102b2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:02:00Z",
  "producer": "triage-service",
  "data": {
    "signo_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "frecuencia_cardiaca": 110,
    "presion_sistolica": 140,
    "presion_diastolica": 90,
    "saturacion_oxigeno": 94,
    "temperatura": 38.5,
    "frecuencia_respiratoria": 18,
    "nivel_conciencia": "alerta"
  }
}
```

---

### 3. triage.evaluacion.iniciada

- **Descripción:** Un profesional de la salud inicia formalmente la evaluación del episodio de triage.

- **Productor:** Contexto de Triage y Decisión Clínica

- **Consumidores:** Contexto de Inferencia y Soporte de IA, Contexto de Auditoría y Gobernanza Médico-Legal

- **Tiempo Real (WS/SSE):** Sí (Mantiene el estado 'en_espera' en el tablero).

```json
{
  "event_id": "evt_103c2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:05:00Z",
  "producer": "triage-service",
  "data": {
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "usuario_id_registro": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "codigo_turno": "TURNO-A",
    "estado": "en_espera"
  }
}
```

---

### 4. ia.clasificacion.solicitada

- **Descripción:** Envío del vector de datos clínicos anonimizados a través del Filtro Zero PII hacia el motor de IA.

- **Productor:** Contexto de Triage y Decisión Clínica

- **Consumidores:** Contexto de Inferencia y Soporte de IA

- **Tiempo Real (WS/SSE):** No (Petición asíncrona backend).

```json
{
  "event_id": "evt_104d2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:06:00Z",
  "producer": "triage-service",
  "data": {
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "token_correlacion_efimero": "tok_sec_abc123",
    "prompt_enviado": "Frecuencia cardiaca: 110, SpO2: 94%, Presion: 140/90, Sintomas: dolor toracico, disnea leve",
    "hash_entrada": "a1b2c3d4e5f67890123456789012345678901234567890123456789012345678"
  }
}
```

---

### 5. ia.clasificacion.sugerida

- **Descripción:** El motor de IA devuelve la sugerencia probabilística ESI (1 al 5) con su justificación estructurada.

- **Productor:** Contexto de Inferencia y Soporte de IA

- **Consumidores:** Contexto de Triage y Decisión Clínica, Contexto de Auditoría y Gobernanza Médico-Legal

- **Tiempo Real (WS/SSE):** Sí (Envía la sugerencia al box de evaluación vía WebSocket).

```json
{
  "event_id": "evt_105e2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:06:05Z",
  "producer": "ai-classification-service",
  "data": {
    "clasificacion_id": "a8f3d1e2-4b5c-6d7e-8f9a-0b1c2d3e4f5a",
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "token_correlacion_efimero": "tok_sec_abc123",
    "nivel_esi_sugerido": 2,
    "justificacion": "Riesgo cardiovascular elevado por taquicardia y desaturacion leve.",
    "modelo_usado": "claude-3-5-sonnet",
    "latencia_ms": 1250,
    "fecha_hora_solicitud": "2026-10-06T20:06:05Z"
  }
}
```

---

### 6. triage.clasificacion.respaldo_aplicada

- **Descripción:** Ocurre cuando el servicio de IA presenta falla o latencia superior a 1500 ms y se conmuta automáticamente al árbol de reglas heurísticas deterministas.

- **Productor:** Contexto de Triage y Decisión Clínica

- **Consumidores:** Contexto de Auditoría y Gobernanza Médico-Legal

- **Tiempo Real (WS/SSE):** Sí (Alerta visual al profesional sobre la activación del modo contingencia).

```json
{
  "event_id": "evt_106f2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:06:30Z",
  "producer": "triage-service",
  "data": {
    "clasificacion_id": "b9f4e2f3-5c6d-7e8f-9a0b-1c2d3e4f5a6b",
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "nivel_esi_sugerido": 3,
    "justificacion": "Clasificacion por Reglas Heurísticas de Respaldo (Fallback determinista por latencia de IA).",
    "modelo_usado": "fallback-rule-engine",
    "latencia_ms": 1550
  }
}
```

---

### 7. triage.evaluacion.confirmada

- **Descripción:** El profesional de salud valida y confirma la categoría ESI final del paciente en la decisión clínica.

- **Productor:** Contexto de Triage y Decisión Clínica

- **Consumidores:** Contexto de Admisión y Registro, Contexto de Auditoría y Gobernanza Médico-Legal

- **Tiempo Real (WS/SSE):** Sí (Asigna prioridad en la lista de espera).

```json
{
  "event_id": "evt_107g2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:08:00Z",
  "producer": "triage-service",
  "data": {
    "decision_id": "c0a5f3e4-6d7e-8f9a-0b1c-2d3e4f5a6b7c",
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "usuario_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "nivel_esi_definitivo": 2,
    "es_sobrescritura": false,
    "fecha_hora_decision": "2026-10-06T20:08:00Z"
  }
}
```

---

### 8. triage.override.ejecutado

- **Descripción:** Modificación manual explícita (sobrescritura) efectuada por el facultativo sobre la sugerencia de la IA, con su debida justificación médica.

- **Productor:** Contexto de Triage y Decisión Clínica

- **Consumidores:** Contexto de Auditoría y Gobernanza Médico-Legal

- **Tiempo Real (WS/SSE):** Sí (Registra discrepancia Humano-IA en tiempo real).

```json
{
  "event_id": "evt_108h2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:08:15Z",
  "producer": "triage-service",
  "data": {
    "decision_id": "d1b6f4e5-7e8f-9a0b-1c2d-3e4f5a6b7c8d",
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "usuario_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "clasificacion_id": "a8f3d1e2-4b5c-6d7e-8f9a-0b1c2d3e4f5a",
    "nivel_esi_definitivo": 2,
    "es_sobrescritura": true,
    "justificacion": "Se aumenta urgencia por dolor toracico con antecedentes familiares directos.",
    "fecha_hora_decision": "2026-10-06T20:08:15Z"
  }
}
```

---

### 9. paciente.atencion.iniciada

- **Descripción:** Inicio del proceso de atención médica en box de urgencia.

- **Productor:** Contexto de Triage y Decisión Clínica

- **Consumidores:** Contexto de Admisión y Registro, Contexto de Auditoría y Gobernanza Médico-Legal

- **Tiempo Real (WS/SSE):** Sí (Actualiza estado a 'en_atencion' y retira de lista de espera activa).

```json
{
  "event_id": "evt_109i2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:15:00Z",
  "producer": "triage-service",
  "data": {
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "usuario_id_registro": "8d0f7780-8536-51ef-a55c-f18ad20a1bf8",
    "estado": "en_atencion"
  }
}
```

---

### 10. notificacion.alerta.disparada

- **Descripción:** Generación de alerta crítica en el tablero de urgencias ante el ingreso de pacientes clasificados con ESI 1 o ESI 2.

- **Productor:** Contexto de Triage y Decisión Clínica

- **Consumidores:** Tablero Frontend (WebSocket / Redis)

- **Tiempo Real (WS/SSE):** Sí (Emisión inmediata de señal sonora/visual).

```json
{
  "event_id": "evt_110j2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:08:02Z",
  "producer": "triage-service",
  "data": {
    "nivel_alerta": "CRITICAL",
    "mensaje": "Paciente ESI 2 ingresado en espera de box",
    "rol_destino": "medico"
  }
}
```

---

### 11. audit.registro.creado

- **Descripción:** Registro inmutable (append-only) generado en la bitácora de auditoría con la sugerencia de IA, el prompt anonimizado enviado, la decisión final y encadenamiento criptográfico.

- **Productor:** Contexto de Auditoría y Gobernanza Médico-Legal

- **Consumidores:** Almacenamiento Seguro / Sistema Legal

- **Tiempo Real (WS/SSE):** No (Persistencia asíncrona).

```json
{
  "event_id": "evt_111k2026",
  "version": "1.0",
  "timestamp": "2026-10-06T20:08:16Z",
  "producer": "audit-service",
  "data": {
    "registro_id": "e2c7a5f6-8f9a-0b1c-2d3e-4f5a6b7c8d9e",
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "decision_id": "d1b6f4e5-7e8f-9a0b-1c2d-3e4f5a6b7c8d",
    "sugerencia_ia": "Nivel ESI 3 - Riesgo moderado",
    "prompt_enviado": "Frecuencia cardiaca: 110, SpO2: 94%, Presion: 140/90, Sintomas: dolor toracico",
    "decision_final": "Nivel ESI 2 - Sobrescritura médica aplicada",
    "usuario_id_actor": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "evento_tipo": "triage.override.ejecutado",
    "hash_anterior": "883a90e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0",
    "hash_actual": "f9e8d7c6b5a4039281706f5e4d3c2b1a0f9e8d7c6b5a4039281706f5e4d3c2b1",
    "fecha_hora_evento": "2026-10-06T20:08:16Z"
  }
}
```

---

### 12. paciente.alta.registrada

- **Descripción:** Finalización formal del flujo de urgencia y alta o derivación del paciente.

- **Productor:** Contexto de Admisión y Registro de Pacientes

- **Consumidores:** Contexto de Triage y Decisión Clínica

- **Tiempo Real (WS/SSE):** Sí (Cierra el estado a 'cerrado' en el tablero).

```json
{
  "event_id": "evt_112l2026",
  "version": "1.0",
  "timestamp": "2026-10-06T21:00:00Z",
  "producer": "admision-service",
  "data": {
    "episodio_id": "550e8400-e29b-41d4-a716-446655440000",
    "estado": "cerrado",
    "fecha_hora_evento": "2026-10-06T21:00:00Z"
  }
}
```
