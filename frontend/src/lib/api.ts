// Cliente HTTP del backend. Las rutas son relativas (/api/v1/...) y Next las
// reenvía al backend (ver rewrites en next.config.ts).

export type SexoBiologico = "male" | "female";
export type NivelConciencia = "alerta" | "verbal" | "dolor" | "inconsciente";

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

export interface FormularioClinico {
  patient_id: string;
  usuario_id?: string;
  motivo_consulta?: string;
  signos_vitales: SignosVitales;
}

export interface FormularioClinicoRespuesta {
  episodio_id: string;
  signos_vitales_id: string;
  patient_id: string;
  estado: string;
  fecha_hora_ingreso: string;
  signos_vitales: SignosVitales;
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

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      cache: "no-store", // las respuestas llevan RUT y nombre: no deben quedar en la caché HTTP
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
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

/** Devuelve [] si no hay un paciente con ese RUT. */
export function buscarPaciente(rut: string): Promise<PacienteEncontrado[]> {
  return pedir(`/api/v1/patients?rut=${encodeURIComponent(rut)}`);
}

export function crearPaciente(datos: PacienteNuevo): Promise<PacienteCreado> {
  return pedir("/api/v1/patients", { method: "POST", body: JSON.stringify(datos) });
}

export function enviarFormulario(
  datos: FormularioClinico,
): Promise<FormularioClinicoRespuesta> {
  return pedir("/api/v1/triage/formulario", {
    method: "POST",
    body: JSON.stringify(datos),
  });
}