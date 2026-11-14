import React from "react";
import type { EstadoGuardado } from "@/hooks/useGuardarDecision";

interface Props {
  estado: EstadoGuardado;
  onReintentar: () => void;
}

/** Mensaje bajo el botón de guardar: dice qué pasó y qué debe hacer la enfermera. */
export const AvisoGuardadoDecision = ({ estado, onReintentar }: Props) => {
  if (estado.fase === "inactivo") return null;

  if (estado.fase === "guardando") {
    return <p role="status" className="text-sm text-slate-600">Guardando decisión…</p>;
  }
  if (estado.fase === "guardado") {
    return <p role="status" className="text-sm font-semibold text-emerald-700">Decisión guardada.</p>;
  }
  if (estado.fase === "rechazado") {
    return (
      <p role="alert" className="text-sm font-semibold text-red-700">
        No se pudo guardar: {estado.mensaje}
      </p>
    );
  }

  const segundos = estado.proximoEnMs ? Math.round(estado.proximoEnMs / 1000) : null;
  return (
    <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 space-y-2">
      <p className="font-semibold">Sin conexión: su decisión NO se ha guardado todavía.</p>
      <p>
        Se conserva en esta pantalla. No cierre ni recargue la página.
        {estado.fase === "reintentando" && segundos !== null
          ? ` Reintentando en ${segundos} s (intento ${estado.intentos} de 5).`
          : " Se reintentará al volver la conexión."}
      </p>
      <button
        type="button"
        onClick={onReintentar}
        className="rounded-lg bg-amber-600 px-3 py-1.5 font-bold text-white hover:bg-amber-700 cursor-pointer"
      >
        Reintentar ahora
      </button>
    </div>
  );
};