// Cliente HTTP del backend. Las rutas son relativas (/api/v1/...) y Next las
// reenvía al backend (ver rewrites en next.config.ts).
//
// Las rutas y los nombres de los tipos son los de api/openapi.yaml (el mismo contrato
// del que se genera packages/api-client). Si cambia el contrato, hay que cambiarlos aquí.

// --- Rutas del contrato ---
export const RUTAS = {
  health: "/api/v1/health",
  login: "/api/v1/auth/login",
  sesion: "/api/v1/auth/me",
  logout: "/api/v1/auth/logout",
  pacientes: "/api/v1/patients",
  formulario: "/api/v1/triage/formulario",
  evaluar: (episodioId: string) => `/api/v1/triage/${episodioId}/evaluate`,
  decision: (episodioId: string) => `/api/v1/triage/${episodioId}/decision`,
  decisionFallo: (episodioId: string) => `/api/v1/triage/${episodioId}/decision/fallo`,
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
  /** Nula si el paciente no tiene fecha de nacimiento registrada. */
  age: number | null;
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

/**
 * Fila de la pantalla pública (GET /sala-espera, sin login). Solo turno anonimizado:
 * nunca RUT, nombre, patient_id ni episodio_id.
 */
export interface SalaEsperaEntry {
  /** Correlativo de llegada del día, p. ej. "A-12". */
  turno: string;
  /** Nivel vigente (final o, si no hay, el sugerido). Nulo si aún no se evalúa. */
  nivel_esi: EsiLevel | null;
  estado: EstadoEpisodio;
  /** Lugar en la fila (1 = el próximo). Nulo si ya está en atención. */
  posicion: number | null;
  minutos_espera: number;
  /** Minutos que le quedan según el objetivo de su categoría. Nulo sin nivel ESI. */
  tiempo_estimado_min: number | null;
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

export interface SesionResponse {
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

// La sesión vive en una cookie httpOnly (access_token) que pone el backend en el login: este
// código no ve ni guarda el token. Como se llama a /api/v1 por el rewrite de Next (mismo
// origen), el navegador envía la cookie solo.

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      cache: "no-store", // las respuestas llevan RUT y nombre: no deben quedar en la caché HTTP
      credentials: "same-origin",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor.");
  }

  // Sesión vencida o ausente: de vuelta al login (el login y /auth/me manejan su propio 401).
  if (
    res.status === 401 &&
    url !== RUTAS.login &&
    url !== RUTAS.sesion &&
    typeof window !== "undefined"
  ) {
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- recarga completa a propósito: la sesión venció
    window.location.href = "/login";
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
  if (res.status === 204) return undefined as T;
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

/**
 * POST /auth/login. El cuerpo trae también el token (contrato), pero aquí no se usa ni se
 * guarda: la sesión queda en la cookie httpOnly. Solo se devuelven el rol y el id.
 */
export function iniciarSesion(
  datos: LoginInput,
): Promise<Pick<LoginResponse, "usuario_id" | "rol" | "expires_in">> {
  return pedir(RUTAS.login, { method: "POST", body: JSON.stringify(datos) });
}

/** GET /auth/me: usuario y rol de la sesión (el frontend no puede leer la cookie). */
export function obtenerSesion(): Promise<SesionResponse> {
  return pedir(RUTAS.sesion);
}

/** POST /auth/logout: el backend borra la cookie. */
export function cerrarSesion(): Promise<void> {
  return pedir(RUTAS.logout, { method: "POST" });
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

/** POST /triage/{episodio_id}/decision/fallo */
export function registrarFalloDecision(
  episodioId: string,
  datos: DecisionInput,
): Promise<{ registro_id: string; evento_tipo: string }> {
  return pedir(RUTAS.decisionFallo(episodioId), {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

/** GET /triage/cola */
export function obtenerCola(filtros: FiltrosCola = {}): Promise<ColaTriageItem[]> {
  return pedir(conQuery(RUTAS.cola, { ...filtros }));
}

/** GET /sala-espera (público: no envía ni necesita sesión). */
export function obtenerSalaEspera(init?: RequestInit): Promise<SalaEsperaEntry[]> {
  return pedir(RUTAS.salaEspera, { credentials: "omit", ...init });
}

/** GET /audit-logs */
export function obtenerAuditLogs(filtros: FiltrosAuditoria = {}): Promise<AuditLogEntry[]> {
  return pedir(conQuery(RUTAS.auditLogs, { ...filtros }));
}
/** GET /triage/{episodio_id}/decision */
export function obtenerDecision(
  episodioId: string,
): Promise<DecisionResponse> {
  return pedir(RUTAS.decision(episodioId));
}
