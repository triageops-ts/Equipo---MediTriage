"use client";

// Conecta guardarConReintentos con la pantalla de la enfermera.
import { useCallback, useEffect, useRef, useState } from "react";
import type { DecisionInput, DecisionResponse } from "@/lib/api";
import { enviarAvisosPendientes, guardarConReintentos } from "@/lib/decisionQueue";

export type FaseGuardado =
  | "inactivo"
  | "guardando"
  | "reintentando"
  | "guardado"
  | "pendiente" // sin conexión y sin reintentos automáticos: hay que reintentar a mano
  | "rechazado";

export interface EstadoGuardado {
  fase: FaseGuardado;
  intentos: number;
  proximoEnMs: number | null;
  mensaje: string | null;
  decision: DecisionResponse | null;
}

const INICIAL: EstadoGuardado = {
  fase: "inactivo",
  intentos: 0,
  proximoEnMs: null,
  mensaje: null,
  decision: null,
};

export function useGuardarDecision() {
  const [estado, setEstado] = useState<EstadoGuardado>(INICIAL);
  // La decisión pendiente solo vive en memoria (ver lib/decisionQueue.ts).
  const pendiente = useRef<{ episodioId: string; datos: DecisionInput } | null>(null);
  const control = useRef<AbortController | null>(null);
  const enCurso = useRef(false);

  const ejecutar = useCallback(async () => {
    const p = pendiente.current;
    if (!p || enCurso.current) return;
    enCurso.current = true;
    control.current = new AbortController();
    setEstado({ ...INICIAL, fase: "guardando" });

    const r = await guardarConReintentos({
      episodioId: p.episodioId,
      datos: p.datos,
      señal: control.current.signal,
      alReintentar: ({ intentos, proximoEnMs }) =>
        setEstado((s) => ({ ...s, fase: "reintentando", intentos, proximoEnMs })),
    });
    enCurso.current = false;

    if (r.estado === "guardado") {
      pendiente.current = null; // ya está en el servidor: se borra del navegador
      setEstado({ ...INICIAL, fase: "guardado", intentos: r.intentos, decision: r.decision });
    } else if (r.estado === "fallido") {
      setEstado({ ...INICIAL, fase: "pendiente", intentos: r.intentos });
    } else if (r.estado === "rechazado") {
      pendiente.current = null;
      setEstado({ ...INICIAL, fase: "rechazado", intentos: r.intentos, mensaje: r.mensaje });
    }
  }, []);

  const guardar = useCallback(
    (episodioId: string, datos: DecisionInput) => {
      pendiente.current = { episodioId, datos };
      return ejecutar();
    },
    [ejecutar],
  );

  const reintentarAhora = useCallback(() => {
    control.current?.abort(); // corta la espera actual
    return ejecutar();
  }, [ejecutar]);

  // Al volver la conexión: reintenta la decisión pendiente y envía los avisos de auditoría.
  useEffect(() => {
    const alVolverInternet = () => {
      void enviarAvisosPendientes();
      if (pendiente.current && !enCurso.current) void ejecutar();
    };
    window.addEventListener("online", alVolverInternet);
    return () => window.removeEventListener("online", alVolverInternet);
  }, [ejecutar]);

  // Mientras haya una decisión sin guardar, el navegador avisa antes de cerrar o recargar.
  const hayPendiente = estado.fase === "reintentando" || estado.fase === "pendiente" || estado.fase === "guardando";
  useEffect(() => {
    if (!hayPendiente) return;
    const avisar = (ev: BeforeUnloadEvent) => {
      ev.preventDefault();
      ev.returnValue = "";
    };
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [hayPendiente]);

  useEffect(() => () => control.current?.abort(), []);

  return { ...estado, hayPendiente, guardar, reintentarAhora };
}