// Cliente TypeScript de la API de MediTriage.
//
// `schema.d.ts` se GENERA desde api/openapi.yaml y no se edita a mano:
//   cd packages/api-client && npm run generate
// Este archivo solo exporta los tipos con los mismos nombres que tienen en el contrato.

import type { components, operations, paths } from "./schema";

export type { components, operations, paths };

type Schemas = components["schemas"];

// --- Enums compartidos ---
export type EsiLevel = Schemas["EsiLevel"];
export type NivelConciencia = Schemas["NivelConciencia"];
export type SeveridadSintoma = Schemas["SeveridadSintoma"];
export type EstadoEpisodio = Schemas["EstadoEpisodio"];
export type SexoBiologico = Schemas["SexoBiologico"];
export type RolUsuario = Schemas["RolUsuario"];

// --- Sistema y autenticación ---
export type HealthResponse = Schemas["HealthResponse"];
export type LoginInput = Schemas["LoginInput"];
export type LoginResponse = Schemas["LoginResponse"];

// --- Pacientes ---
export type PatientInput = Schemas["PatientInput"];
export type Patient = Schemas["Patient"];
export type PatientFound = Schemas["PatientFound"];
export type PatientSummary = Schemas["PatientSummary"];

// --- Triage ---
export type SignosVitalesInput = Schemas["SignosVitalesInput"];
export type SintomaInput = Schemas["SintomaInput"];
export type FormularioClinicoInput = Schemas["FormularioClinicoInput"];
export type FormularioClinicoResponse = Schemas["FormularioClinicoResponse"];
export type ClasificacionIA = Schemas["ClasificacionIA"];
export type DecisionInput = Schemas["DecisionInput"];
export type DecisionResponse = Schemas["DecisionResponse"];
export type ColaTriageItem = Schemas["ColaTriageItem"];
export type SalaEsperaEntry = Schemas["SalaEsperaEntry"];

// --- Auditoría y errores ---
export type AuditLogEntry = Schemas["AuditLogEntry"];
export type Problem = Schemas["Problem"];

// --- Rutas (relativas a la URL base del servidor) ---
export const URL_BASE_API = "https://api.meditriage.com/api/v1";
export const URL_BASE_LOCAL = "http://localhost:8000/api/v1";

export const RUTAS = {
  health: "/health",
  login: "/auth/login",
  pacientes: "/patients",
  formulario: "/triage/formulario",
  evaluar: (episodioId: string) => `/triage/${episodioId}/evaluate`,
  decision: (episodioId: string) => `/triage/${episodioId}/decision`,
  cola: "/triage/cola",
  salaEspera: "/sala-espera",
  auditLogs: "/audit-logs",
} as const;
