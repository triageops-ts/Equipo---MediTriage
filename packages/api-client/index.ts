export type NivelEsi = 1 | 2 | 3 | 4 | 5;
export type NivelConciencia = 'Alerta' | 'Verbal' | 'Dolor' | 'Inconsciente';
export type EstadoTriage = 'esperando' | 'atendiendo' | 'dado_de_alta';

export interface ResumenPaciente {
  id_paciente: string;
  edad: number;
  sexo_biologico: 'masculino' | 'femenino';
}

export interface EntradaSintoma {
  codigo_sintoma: string;
  severidad: 'leve' | 'moderada' | 'severa';
  tiempo_evolucion_horas?: number;
}

export interface EntradaSintomas {
  presion_sistolica: number;
  presion_diastolica: number;
  frecuencia_cardiaca: number;
  frecuencia_respiratoria: number;
  temperatura: number;
  saturacion_oxigeno: number;
  escala_dolor: number;
  nivel_conciencia: NivelConciencia;
  sintomas?: EntradaSintoma[];
  antecedentes_relevantes_codificados?: Record<string, boolean>;
}

export interface RecomendacionIA {
  nivel_esi_sugerido: NivelEsi;
  justificacion_ia: string;
  modelo_usado?: string;
  tiempo_respuesta?: string;
}

export interface EvaluacionTriage {
  id_triage: string;
  paciente: ResumenPaciente;
  estado: EstadoTriage;
  sintomas: EntradaSintomas;
  recomendacion_ia: RecomendacionIA;
  nivel_esi_final?: NivelEsi | null;
}

export interface ProblemaError {
  tipo?: string;
  titulo: string;
  estado: number;
  detalle?: string;
  instancia?: string;
  errores?: Array<{ campo: string; mensaje: string }>;
}

export const URL_BASE_API = "https://api.meditriage.com/v1";
