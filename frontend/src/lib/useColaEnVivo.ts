"use client";

// Cola del tablero médico en tiempo real (S08-9).
//
// 1. Carga la lista inicial con GET /triage/cola (S10-3), ya ordenada por urgencia.
// 2. Se conecta al WebSocket /api/v1/ws/tablero. Los eventos no traen datos del paciente
//    (solo ids y nivel ESI, sin PII), así que ante cada evento se vuelve a pedir la cola.
// 3. Si el WebSocket se cae, reintenta con espera creciente (1 s, 2 s, 4 s... hasta 30 s).
// 4. Además recarga cada 30 s: actualiza los minutos de espera y cubre eventos perdidos
//    (Redis Pub/Sub no guarda mensajes mientras no hay conexión).

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, obtenerCola, obtenerResumenCola, type ColaTriageItem, type ResumenColaTriage } from "@/lib/api";
import { esCritico, nivelVigente } from "@/lib/esi";

export const LIMITE_COLA = 100; // máximo que acepta el endpoint
const RECARGA_PERIODICA_MS = 30_000;
const ESPERA_INICIAL_MS = 1_000;
const ESPERA_MAXIMA_MS = 30_000;
/** Cuánto tiempo se resalta como "nuevo" un paciente ESI 1–2 recién llegado. */
const RESALTE_NUEVO_MS = 20_000;

export type EstadoConexion = "conectando" | "en_vivo" | "sin_conexion";

/**
 * URL del WebSocket. Por defecto usa el mismo origen que la página. Si en desarrollo el
 * proxy de Next no deja pasar el WebSocket, se puede apuntar directo al backend con
 * NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws/tablero en frontend/.env.local.
 */
function urlWebSocket(): string {
  const configurada = process.env.NEXT_PUBLIC_WS_URL;
  if (configurada) return configurada;
  const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocolo}//${window.location.host}/api/v1/ws/tablero`;
}

/**
 * @param alNuevoCritico se llama cuando aparece un paciente ESI 1–2 en espera que no
 *   estaba en la carga anterior (no en la primera carga), con el nivel más urgente.
 */
export function useColaEnVivo(alNuevoCritico?: (nivel: 1 | 2) => void) {
  const [items, setItems] = useState<ColaTriageItem[] | null>(null);
  const [resumen, setResumen] = useState<ResumenColaTriage | null>(null);
  const [nuevos, setNuevos] = useState<ReadonlySet<string>>(() => new Set());
  // Episodios críticos de la carga anterior (null = todavía no hubo carga).
  const criticosPrevios = useRef<Set<string> | null>(null);
  const avisar = useRef(alNuevoCritico);
  const [error, setError] = useState<string | null>(null);
  const [conexion, setConexion] = useState<EstadoConexion>("conectando");
  const [actualizado, setActualizado] = useState<Date | null>(null);
  const [errorResumen, setErrorResumen] = useState<string | null>(null);

  useEffect(() => {
    avisar.current = alNuevoCritico;
  }, [alNuevoCritico]);

  const cargar = useCallback(async () => {
    const detectarNuevosCriticos = (datos: ColaTriageItem[]) => {
      const criticos = datos.filter(esCritico);
      const previos = criticosPrevios.current;
      criticosPrevios.current = new Set(criticos.map((i) => i.episodio_id));
      if (previos === null) return; // primera carga: el banner ya los muestra

      const llegados = criticos.filter((i) => !previos.has(i.episodio_id));
      if (llegados.length === 0) return;

      const ids = llegados.map((i) => i.episodio_id);
      setNuevos((actual) => new Set([...actual, ...ids]));
      setTimeout(() => {
        setNuevos((actual) => {
          const siguiente = new Set(actual);
          ids.forEach((id) => siguiente.delete(id));
          return siguiente;
        });
      }, RESALTE_NUEVO_MS);

      const masUrgente = Math.min(...llegados.map((i) => nivelVigente(i) ?? 2));
      avisar.current?.(masUrgente === 1 ? 1 : 2);
    };

    try {
      const [resultadoCola, resultadoResumen] = await Promise.allSettled([
        obtenerCola({ limit: LIMITE_COLA }),
        obtenerResumenCola(),
      ]);
      if (resultadoCola.status === "rejected") throw resultadoCola.reason;
      const datos = resultadoCola.value;
      setItems(datos);
      if (resultadoResumen.status === "fulfilled") {
        setResumen(resultadoResumen.value);
        setErrorResumen(null);
      } else {
        setResumen(null);
        setErrorResumen("No se pudo actualizar el resumen global de la cola.");
      }
      detectarNuevosCriticos(datos);
      setError(null);
      setActualizado(new Date());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar la cola de pacientes.");
    }
  }, []);

  // Carga inicial y recarga periódica.
  useEffect(() => {
    // La primera carga va en un temporizador (no directo en el efecto) para que el
    // setState ocurra en un callback, como pide la regla react-hooks/set-state-in-effect.
    const inicial = setTimeout(() => void cargar(), 0);
    const intervalo = setInterval(() => void cargar(), RECARGA_PERIODICA_MS);
    return () => {
      clearTimeout(inicial);
      clearInterval(intervalo);
    };
  }, [cargar]);

  // Canal en vivo.
  useEffect(() => {
    let socket: WebSocket | null = null;
    let terminado = false;
    let espera = ESPERA_INICIAL_MS;
    let reintento: ReturnType<typeof setTimeout> | undefined;
    let recarga: ReturnType<typeof setTimeout> | undefined;

    const conectar = () => {
      if (terminado) return;
      socket = new WebSocket(urlWebSocket());

      socket.onmessage = (mensaje) => {
        let tipo: unknown;
        try {
          tipo = JSON.parse(String(mensaje.data))?.event_type;
        } catch {
          return; // mensaje que no es JSON: se ignora
        }
        if (tipo === "conexion.lista") {
          setConexion("en_vivo");
          espera = ESPERA_INICIAL_MS;
          void cargar(); // por si algo cambió mientras no había conexión
          return;
        }
        // Varios eventos seguidos se agrupan en una sola recarga.
        clearTimeout(recarga);
        recarga = setTimeout(() => void cargar(), 300);
      };

      socket.onclose = () => {
        if (terminado) return;
        setConexion("sin_conexion");
        reintento = setTimeout(conectar, espera);
        espera = Math.min(espera * 2, ESPERA_MAXIMA_MS);
      };
    };

    conectar();
    return () => {
      terminado = true;
      clearTimeout(reintento);
      clearTimeout(recarga);
      socket?.close();
    };
  }, [cargar]);

  return { items, resumen, nuevos, error, errorResumen, conexion, actualizado, recargar: cargar };
}
