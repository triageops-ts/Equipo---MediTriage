// Cliente HTTP del backend. Las rutas son relativas (/api/v1/...) y Next las
// reenvía al backend (ver rewrites en next.config.ts).
//
// Las rutas y los nombres de los tipos son los de api/openapi.yaml (el mismo contrato
// del que se genera packages/api-client). Si cambia el contrato, hay que cambiarlos aquí.

// --- Rutas del contrato ---
export const RUTAS = {
  health: "/api/v1/health",
  login: "/api/v1/auth/login",
  pacientes: "/api/v1/patients",
  formulario: "/api/v1/triage/formulario",
  evaluar: (episodioId: string) => `/api/v1/triage/${episodioId}/evaluate`,
  decision: (episodioId: string) => `/api/v1/triage/${episodioId}/decision`,
  cola: "/api/v1/triage/cola",
  salaEspera: "/api/v1/sala-espera",
  auditLogs: "/api/v1/audit-logs",
} as const;

// --- Tipos compartidos ---
export type SexoBiologico = "male" | "female";
export type NivelConciencia = "alerta" | "verbal" | "dolor" | "inconsciente";
export type SeveridadSintoma = "leve" | "moderada" | "severa";
export type EsiLevel = 1 | 2 | 3 | 4 | 5;
export type EstadoEpisodio = "en_espera" | "en_atencion" | "cerrado";
export type RolUsuario = "enfermero" | "medico" | "auditor" | "admin";

// --- Pacientes (GET/POST /patients) ---
export interface PacienteEncontrado {
  patient_id: string;
  rut: string;
  name: string;
  birth_date: string | null;
  biological_sex: SexoBiologico | null;
}

export interface PacienteNuevo {
  rut: string;
  name: string;
  birth_date?: string;
  biological_sex?: SexoBiologico;
  has_consent: boolean;
  consent_version?: string;
}

export interface PacienteCreado extends PacienteEncontrado {
  has_consent: boolean;
  consent_id: string;
  consent_version: string;
  consent_accepted_at: string;
}

// --- Formulario clínico (POST /triage/formulario) ---
export interface SignosVitales {
  presion_sistolica: number;
  presion_diastolica: number;
  frecuencia_cardiaca: number;
  frecuencia_respiratoria: number;
  temperatura: number;
  saturacion_oxigeno: number;
  escala_dolor: number;
  nivel_conciencia: NivelConciencia;
}

export interface SintomaClinico {
  codigo_sintoma: string;
  severidad: SeveridadSintoma;
  tiempo_evolucion_horas?: number;
}

export interface FormularioClinico {
  patient_id: string;
  usuario_id?: string;
  motivo_consulta?: string;
  signos_vitales: SignosVitales;
  sintomas?: SintomaClinico[];
}
export interface FormularioClinicoRespuesta {
  episodio_id: string;
  signos_vitales_id: string;
  patient_id: string;
  estado: string;
  fecha_hora_ingreso: string;
  signos_vitales: SignosVitales;
}

// --- Evaluación con IA (POST /triage/{episodio_id}/evaluate) ---
export interface ClasificacionIA {
  clasificacion_id: string;
  episodio_id: string;
  nivel_esi_sugerido: EsiLevel;
  justificacion_ia: string;
  modelo_usado: string;
  fallback_aplicado: boolean;
  latencia_ms: number;
  fecha_hora_solicitud: string;
}

// --- Decisión final (POST /triage/{episodio_id}/decision) ---
export interface DecisionInput {
  nivel_esi_final: EsiLevel;
  /** Obligatoria (mínimo 10 caracteres) si el nivel final difiere del sugerido por la IA. */
  justificacion?: string;
  usuario_id?: string;
}

export interface DecisionResponse {
  decision_id: string;
  episodio_id: string;
  nivel_esi_sugerido: EsiLevel;
  nivel_esi_final: EsiLevel;
  coincide_con_ia: boolean;
  modificado_manualmente: boolean;
  justificacion: string | null;
  usuario_id: string | null;
  fecha_hora_decision: string;
}

// --- Cola de triage y sala de espera (GET /triage/cola, GET /sala-espera) ---
export interface ResumenPaciente {
  patient_id: string;
  age: number;
  biological_sex?: SexoBiologico | null;
}

export interface ColaTriageItem {
  episodio_id: string;
  patient: ResumenPaciente;
  estado: EstadoEpisodio;
  nivel_esi_sugerido?: EsiLevel | null;
  nivel_esi_final?: EsiLevel | null;
  fecha_hora_ingreso: string;
  minutos_espera: number;
}

export interface SalaEsperaEntry {
  episodio_id: string;
  posicion: number;
  estado: EstadoEpisodio;
  minutos_espera: number;
}

export interface FiltrosCola {
  estado?: EstadoEpisodio;
  nivel_esi?: EsiLevel;
  skip?: number;
  limit?: number;
}

// --- Auditoría (GET /audit-logs) ---
export interface AuditLogEntry {
  registro_id: string;
  episodio_id: string;
  decision_id?: string | null;
  evento_tipo: string;
  usuario_id_actor?: string | null;
  sugerencia_ia?: string | null;
  prompt_enviado?: string | null;
  decision_final?: string | null;
  hay_discrepancia: boolean;
  hash_anterior: string;
  hash_actual: string;
  fecha_hora_evento: string;
}

export interface FiltrosAuditoria {
  episodio_id?: string;
  usuario_id?: string;
  hay_discrepancia?: boolean;
  skip?: number;
  limit?: number;
}

// --- Sistema y autenticación (GET /health, POST /auth/login) ---
export interface EstadoServicio {
  status: string;
  service: string;
  version: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  usuario_id: string;
  rol: RolUsuario;
}

export interface ErrorCampo {
  field: string;
  message: string;
}

/** Error devuelto por el backend (formato Problem JSON). */
export class ApiError extends Error {
  status: number;
  errores: ErrorCampo[];

  constructor(status: number, mensaje: string, errores: ErrorCampo[] = []) {
    super(mensaje);
    this.status = status;
    this.errores = errores;
  }
}

// Token JWT de la sesión (lo entrega POST /auth/login). Si hay uno, se envía como Bearer.
let tokenActual: string | null = null;

export function establecerToken(token: string | null): void {
  tokenActual = token;
}

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      cache: "no-store", // las respuestas llevan RUT y nombre: no deben quedar en la caché HTTP
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(tokenActual ? { Authorization: `Bearer ${tokenActual}` } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor.");
  }

  if (!res.ok) {
    let detalle = `Error ${res.status}`;
    let errores: ErrorCampo[] = [];
    try {
      const cuerpo = await res.json();
      if (typeof cuerpo.detail === "string") detalle = cuerpo.detail;
      if (Array.isArray(cuerpo.errors)) errores = cuerpo.errors;
    } catch {
      // la respuesta no era JSON; se deja el mensaje genérico
    }
    throw new ApiError(res.status, detalle, errores);
  }
  return (await res.json()) as T;
}

function conQuery(ruta: string, params: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params)) {
    if (valor !== undefined) query.set(clave, String(valor));
  }
  const texto = query.toString();
  return texto ? `${ruta}?${texto}` : ruta;
}

// --- Funciones del cliente: una por operación del contrato ---

/** GET /health */
export function obtenerEstadoServicio(): Promise<EstadoServicio> {
  return pedir(RUTAS.health);
}

/** POST /auth/login */
export function iniciarSesion(datos: LoginInput): Promise<LoginResponse> {
  return pedir(RUTAS.login, { method: "POST", body: JSON.stringify(datos) });
}

/** GET /patients. Devuelve [] si no hay un paciente con ese RUT. */
export function buscarPaciente(rut: string): Promise<PacienteEncontrado[]> {
  return pedir(conQuery(RUTAS.pacientes, { rut }));
}

/** POST /patients */
export function crearPaciente(datos: PacienteNuevo): Promise<PacienteCreado> {
  return pedir(RUTAS.pacientes, { method: "POST", body: JSON.stringify(datos) });
}

/** POST /triage/formulario */
export function enviarFormulario(
  datos: FormularioClinico,
): Promise<FormularioClinicoRespuesta> {
  return pedir(RUTAS.formulario, {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

/** POST /triage/{episodio_id}/evaluate */
export function evaluarTriage(episodioId: string): Promise<ClasificacionIA> {
  return pedir(RUTAS.evaluar(episodioId), { method: "POST" });
}

/** POST /triage/{episodio_id}/decision */
export function registrarDecision(
  episodioId: string,
  datos: DecisionInput,
): Promise<DecisionResponse> {
  return pedir(RUTAS.decision(episodioId), {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

/** GET /triage/cola */
export function obtenerCola(filtros: FiltrosCola = {}): Promise<ColaTriageItem[]> {
  return pedir(conQuery(RUTAS.cola, { ...filtros }));
}

/** GET /sala-espera */
export function obtenerSalaEspera(): Promise<SalaEsperaEntry[]> {
  return pedir(RUTAS.salaEspera);
}

/** GET /audit-logs */
export function obtenerAuditLogs(filtros: FiltrosAuditoria = {}): Promise<AuditLogEntry[]> {
  return pedir(conQuery(RUTAS.auditLogs, { ...filtros }));
}
