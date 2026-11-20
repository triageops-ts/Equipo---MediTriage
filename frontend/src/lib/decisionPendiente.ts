// S07-11: respaldo temporal en el navegador de una decisión clínica que aún no se guarda.
//
// Si se cae la conexión justo cuando la enfermera guarda su decisión, la decisión no se
// puede perder: se respalda aquí ANTES de enviarla y se borra apenas el servidor la
// confirma (o la rechaza de forma definitiva: 404, 409, 422).
//
// Privacidad (ver docs/data/frontend-pii-review.md):
// - Se usa el almacenamiento de sesión de la pestaña, no el persistente: se borra solo al
//   cerrar la pestaña y no lo ven otras pestañas ni otros usuarios del equipo.
// - Solo se guarda lo mínimo para reenviar: id del episodio (UUID), nivel ESI, justificación
//   clínica y si el fallo ya quedó en la auditoría. Nunca RUT, nombre ni datos del formulario.
// - Vence a las 12 horas (un turno); un respaldo vencido o con formato inválido se descarta.
import type { DecisionInput, EsiLevel } from "@/lib/api";

const CLAVE = "meditriage:decision-pendiente";
const VIGENCIA_MS = 12 * 60 * 60 * 1000;

export interface DecisionRespaldada {
  episodio_id: string;
  decision: DecisionInput;
  /** true si el fallo ya se registró en la auditoría (POST /decision/fallo). */
  fallo_registrado: boolean;
  /** Momento del respaldo (ms desde epoch), para el vencimiento. */
  respaldada_en: number;
}

function almacen(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage; // pii-ok: solo id de episodio, nivel ESI y justificación (S07-11)
  } catch {
    // Navegador con el almacenamiento bloqueado: se sigue funcionando solo en memoria.
    return null;
  }
}

function esNivelEsi(valor: unknown): valor is EsiLevel {
  return typeof valor === "number" && Number.isInteger(valor) && valor >= 1 && valor <= 5;
}

/** Guarda (o reemplaza) la decisión pendiente. Nunca lanza. */
export function respaldarDecision(respaldo: DecisionRespaldada): void {
  try {
    almacen()?.setItem(CLAVE, JSON.stringify(respaldo));
  } catch {
    // Almacenamiento lleno o bloqueado: la decisión sigue en memoria mientras la página viva.
  }
}

/** Devuelve la decisión pendiente, o null si no hay, venció o el contenido no es válido. */
export function leerDecisionRespaldada(): DecisionRespaldada | null {
  try {
    const texto = almacen()?.getItem(CLAVE);
    if (!texto) return null;

    const r = JSON.parse(texto) as Partial<DecisionRespaldada>;
    const valido =
      typeof r.episodio_id === "string" &&
      r.episodio_id.length > 0 &&
      typeof r.respaldada_en === "number" &&
      typeof r.fallo_registrado === "boolean" &&
      r.decision !== undefined &&
      esNivelEsi(r.decision.nivel_esi_final) &&
      (r.decision.justificacion === undefined ||
        typeof r.decision.justificacion === "string");

    if (!valido || Date.now() - (r.respaldada_en as number) > VIGENCIA_MS) {
      borrarDecisionRespaldada();
      return null;
    }
    return r as DecisionRespaldada;
  } catch {
    borrarDecisionRespaldada();
    return null;
  }
}

/** Marca en el respaldo que el fallo ya quedó registrado en la auditoría. */
export function marcarFalloRegistrado(episodioId: string): void {
  const actual = leerDecisionRespaldada();
  if (actual && actual.episodio_id === episodioId) {
    respaldarDecision({ ...actual, fallo_registrado: true });
  }
}

/** Borra el respaldo (decisión guardada o rechazada de forma definitiva). Nunca lanza. */
export function borrarDecisionRespaldada(): void {
  try {
    almacen()?.removeItem(CLAVE);
  } catch {
    // nada que hacer
  }
}