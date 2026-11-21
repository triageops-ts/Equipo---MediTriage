// Niveles ESI y cómo se muestran en el tablero médico (S08-9).
// Las clases de Tailwind van escritas completas para que el compilador las encuentre.
import type { ColaTriageItem, EsiLevel, SexoBiologico } from "@/lib/api";

interface EstiloEsi {
  nombre: string;
  /** Pastilla de color sólido (lista y paneles). */
  pastilla: string;
  /** Tarjeta del contador superior. */
  contador: string;
  /** Color del número del contador y del nivel en el detalle. */
  texto: string;
  /** Recuadro destacado del detalle. */
  recuadro: string;
}

export const ESI: Record<EsiLevel, EstiloEsi> = {
  1: {
    nombre: "Emergencia",
    pastilla: "bg-red-500 text-white",
    contador: "border-red-500",
    texto: "text-red-500",
    recuadro: "border-red-400 bg-red-50",
  },
  2: {
    nombre: "Muy urgente",
    pastilla: "bg-orange-500 text-white",
    contador: "border-orange-500",
    texto: "text-orange-500",
    recuadro: "border-orange-400 bg-orange-50",
  },
  3: {
    nombre: "Urgente",
    pastilla: "bg-yellow-500 text-white",
    contador: "border-yellow-500",
    texto: "text-yellow-500",
    recuadro: "border-yellow-400 bg-yellow-50",
  },
  4: {
    nombre: "Menor urgencia",
    pastilla: "bg-green-500 text-white",
    contador: "border-green-500",
    texto: "text-green-500",
    recuadro: "border-green-400 bg-green-50",
  },
  5: {
    nombre: "No urgente",
    pastilla: "bg-blue-500 text-white",
    contador: "border-blue-500",
    texto: "text-blue-500",
    recuadro: "border-blue-400 bg-blue-50",
  },
};

export const NIVELES_ESI: EsiLevel[] = [1, 2, 3, 4, 5];

/** Nivel que manda: el final de enfermería si ya decidió; si no, el sugerido por la IA. */
export function nivelVigente(item: ColaTriageItem): EsiLevel | null {
  return item.nivel_esi_final ?? item.nivel_esi_sugerido ?? null;
}

/** ESI 1 y 2 que siguen esperando: son los que disparan la alerta. */
export function esCritico(item: ColaTriageItem): boolean {
  const nivel = nivelVigente(item);
  return item.estado === "en_espera" && nivel !== null && nivel <= 2;
}

/**
 * Código corto para identificar el episodio en pantalla (p. ej. "T-3F9A").
 * Sale del id del episodio: no es el nombre ni el RUT del paciente.
 */
export function codigoEpisodio(episodioId: string): string {
  return `T-${episodioId.replace(/-/g, "").slice(0, 4).toUpperCase()}`;
}

export function sexoCorto(sexo: SexoBiologico | null | undefined): string {
  return sexo === "female" ? "F" : sexo === "male" ? "M" : "—";
}

export function sexoLargo(sexo: SexoBiologico | null | undefined): string {
  return sexo === "female" ? "Femenino" : sexo === "male" ? "Masculino" : "Sexo no registrado";
}

export function edadTexto(edad: number | null | undefined): string {
  return edad === null || edad === undefined ? "Edad s/d" : `${edad} años`;
}

export function esperaTexto(minutos: number): string {
  if (minutos < 60) return `espera ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  return `espera ${horas} h ${resto} min`;
}

export type EstadoRevision = "en_atencion" | "confirmado" | "pendiente" | "sin_evaluar";

/** Estado que se muestra a la derecha de cada fila. */
export function estadoRevision(item: ColaTriageItem): EstadoRevision {
  if (item.estado === "en_atencion") return "en_atencion";
  if (item.nivel_esi_final != null) return "confirmado";
  if (item.nivel_esi_sugerido != null) return "pendiente";
  return "sin_evaluar";
}

export const ETIQUETA_REVISION: Record<EstadoRevision, { texto: string; clase: string }> = {
  en_atencion: { texto: "En atención", clase: "text-blue-600" },
  confirmado: { texto: "Confirmado", clase: "text-green-600" },
  pendiente: { texto: "Pendiente de revisión", clase: "text-amber-600" },
  sin_evaluar: { texto: "Sin evaluar", clase: "text-slate-500" },
};
