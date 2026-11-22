"use client";

// Refresco automático de la pantalla pública (S11-10).
//
// Consulta GET /sala-espera cada INTERVALO_MS. No usa el WebSocket de S08 porque ese
// canal exige sesión de médico y esta pantalla no tiene login.
//
// - Cada respuesta reemplaza la lista completa de una vez: si cambian varios turnos al
//   mismo tiempo, se ven todos juntos y en el orden por prioridad (nunca a medias).
// - Las consultas no se encadenan: la siguiente sale cuando terminó la anterior.
// - Si una respuesta vieja llega después de una nueva, se descarta.
// - Si falla, se mantiene la última lista buena y se reintenta con más espera.

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, obtenerSalaEspera, type SalaEsperaEntry } from "@/lib/api";

export const INTERVALO_MS = 5_000;
const INTERVALO_CON_ERROR_MS = 15_000;
/** Cuánto tiempo se destaca un turno recién llamado. */
const RESALTE_LLAMADO_MS = 15_000;

export function useSalaEspera() {
  const [filas, setFilas] = useState<SalaEsperaEntry[] | null>(null);
  const [actualizado, setActualizado] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recienLlamados, setRecienLlamados] = useState<ReadonlySet<string>>(() => new Set());

  const ultimaPeticion = useRef(0);
  // Turnos en atención de la carga anterior (null = todavía no hubo carga).
  const llamadosPrevios = useRef<Set<string> | null>(null);

  const detectarLlamados = useCallback((datos: SalaEsperaEntry[]) => {
    const ahora = datos.filter((f) => f.estado === "en_atencion").map((f) => f.turno);
    const previos = llamadosPrevios.current;
    llamadosPrevios.current = new Set(ahora);
    if (previos === null) return; // primera carga: no se destaca nada

    const nuevos = ahora.filter((t) => !previos.has(t));
    if (nuevos.length === 0) return;
    setRecienLlamados((actual) => new Set([...actual, ...nuevos]));
    setTimeout(() => {
      setRecienLlamados((actual) => {
        const siguiente = new Set(actual);
        nuevos.forEach((t) => siguiente.delete(t));
        return siguiente;
      });
    }, RESALTE_LLAMADO_MS);
  }, []);

  /** Devuelve true si la carga salió bien. */
  const cargar = useCallback(
    async (senal?: AbortSignal): Promise<boolean> => {
      const numero = ++ultimaPeticion.current;
      try {
        const datos = await obtenerSalaEspera({ signal: senal });
        if (numero !== ultimaPeticion.current) return true; // llegó una más nueva
        setFilas(datos);
        detectarLlamados(datos);
        setActualizado(new Date());
        setError(null);
        return true;
      } catch (e) {
        if (senal?.aborted) return true;
        setError(e instanceof ApiError ? e.message : "No se pudo actualizar la sala de espera.");
        return false;
      }
    },
    [detectarLlamados],
  );

  useEffect(() => {
    const control = new AbortController();
    let temporizador: ReturnType<typeof setTimeout> | undefined;

    const ciclo = async () => {
      const ok = await cargar(control.signal);
      if (control.signal.aborted) return;
      temporizador = setTimeout(ciclo, ok ? INTERVALO_MS : INTERVALO_CON_ERROR_MS);
    };

    // Primera carga en un temporizador (no directo en el efecto) por la regla
    // react-hooks/set-state-in-effect, igual que en useColaEnVivo.
    temporizador = setTimeout(ciclo, 0);
    return () => {
      control.abort();
      clearTimeout(temporizador);
    };
  }, [cargar]);

  return { filas, actualizado, error, recienLlamados };
}
