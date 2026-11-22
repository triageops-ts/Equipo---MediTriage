// Reglas de la pantalla pública de la sala de espera (S11-10, US-04).
// Solo trabaja con turnos anonimizados: aquí no hay ids, RUT ni nombres.
import type { EsiLevel, SalaEsperaEntry } from "@/lib/api";

/** Rango de espera de cada categoría (el mismo objetivo que usa el backend). */
export const RANGO_ESPERA: Record<EsiLevel, string> = {
  1: "Atención inmediata",
  2: "0 – 15 min",
  3: "15 – 60 min",
  4: "60 – 120 min",
  5: "Más de 120 min",
};

function numeroTurno(turno: string): number {
  const n = Number.parseInt(turno.split("-")[1] ?? "", 10);
  return Number.isNaN(n) ? Number.MAX_SAFE_INTEGER : n;
}

/**
 * Orden por prioridad: ESI 1 arriba, sin nivel al final; a igual nivel, la posición que
 * calculó el backend y, si no hay, el que lleva más tiempo esperando. El número de turno
 * desempata, así el orden es siempre el mismo aunque cambien varios turnos a la vez.
 */
export function compararPrioridad(a: SalaEsperaEntry, b: SalaEsperaEntry): number {
  return (
    (a.nivel_esi ?? 6) - (b.nivel_esi ?? 6) ||
    (a.posicion ?? Number.MAX_SAFE_INTEGER) - (b.posicion ?? Number.MAX_SAFE_INTEGER) ||
    b.minutos_espera - a.minutos_espera ||
    numeroTurno(a.turno) - numeroTurno(b.turno)
  );
}

export interface ResumenSala {
  /** Turnos en espera, ya ordenados por prioridad. */
  enEspera: SalaEsperaEntry[];
  /** Turnos llamados (en atención), el más urgente primero. */
  llamados: SalaEsperaEntry[];
  /** Cuántos esperan en cada nivel ESI. */
  porNivel: Record<EsiLevel, number>;
  /** Promedio de minutos de espera de los que aún esperan (0 si no hay nadie). */
  promedioMin: number;
}

/** Arma todo lo que muestra la pantalla a partir de una sola respuesta del backend. */
export function resumirSala(filas: SalaEsperaEntry[]): ResumenSala {
  const enEspera = filas.filter((f) => f.estado === "en_espera").sort(compararPrioridad);
  const llamados = filas.filter((f) => f.estado === "en_atencion").sort(compararPrioridad);

  const porNivel: Record<EsiLevel, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  for (const f of enEspera) if (f.nivel_esi !== null) porNivel[f.nivel_esi] += 1;

  const total = enEspera.reduce((suma, f) => suma + f.minutos_espera, 0);
  const promedioMin = enEspera.length ? Math.round(total / enEspera.length) : 0;

  return { enEspera, llamados, porNivel, promedioMin };
}

/** Texto del tiempo estimado de un turno. */
export function textoEstimado(fila: SalaEsperaEntry): string {
  if (fila.tiempo_estimado_min === null) return "En evaluación";
  if (fila.tiempo_estimado_min === 0) return "Pronto";
  return `~${fila.tiempo_estimado_min} min`;
}

/** Hora corta para "Última actualización: 18:35 hrs". */
export function horaCorta(fecha: Date): string {
  return fecha.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit", hour12: false });
}
