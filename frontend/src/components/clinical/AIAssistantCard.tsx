"use client";

import React, { useState } from "react";
import type { DecisionResponse, EsiLevel } from "@/lib/api";

interface AIAssistantProps {
  esi: number | null;
  gravedad: string | null;
  justificacion: string | null;
  avisoFallback?: string | null;
  error?: string | null;
  sinEpisodio?: boolean;
  onUpdate?: () => void;
  isLoading?: boolean;
  onConfirm?: (nivel: EsiLevel, motivo: string) => void;
  onRetryDecision?: () => void;
  decisionPendiente?: boolean;
  evaluacionReal?: boolean;
  onManualDecision?: (nivel: EsiLevel, motivo: string) => void;
  decisionLoading?: boolean;
  decisionGuardada?: boolean;
  decisionError?: string | null;
  decisionMensaje?: string | null;
  /** Respuesta del backend (201) cuando la decisión ya quedó guardada. */
  decisionResultado?: DecisionResponse | null;
}

const MOTIVOS_PREDEFINIDOS = {
  palidez: "Palidez observada durante la evaluación clínica.",
  facies_dolor: "Facies de dolor observada durante la evaluación clínica.",
  dolor: "Dolor intenso referido por el paciente.",
  deterioro: "Deterioro clínico observado durante la evaluación.",
} as const;

const MOTIVO_MIN_CARACTERES = 10;
const MOTIVO_MAX_CARACTERES = 1000;

export const AIAssistantCard = ({
  esi,
  gravedad,
  justificacion,
  avisoFallback = null,
  error = null,
  sinEpisodio = false,
  onUpdate,
  isLoading = false,
  onConfirm,
  onManualDecision,
  decisionLoading = false,
  decisionGuardada = false,
  decisionError = null,
  decisionMensaje = null,
  decisionResultado = null,
  onRetryDecision,
  decisionPendiente = false,
  evaluacionReal = false,
}: AIAssistantProps) => {
  // El panel de sobrescritura está cerrado hasta que se pulsa "Sobrescribir".
  const [sobrescribiendo, setSobrescribiendo] = useState(false);
  const [nivelManual, setNivelManual] = useState<EsiLevel | null>(null);
  const [tipoMotivo, setTipoMotivo] = useState("");
  const [motivoManual, setMotivoManual] = useState("");

  const nivelSugerido: EsiLevel | null =
    esi !== null && esi >= 1 && esi <= 5 ? (esi as EsiLevel) : null;

  const nivelManualActual: EsiLevel = nivelManual ?? nivelSugerido ?? 3;

  const lineas = (justificacion ?? "")
    .split("\n")
    .map((linea) => linea.trim())
    .filter(Boolean);

  const bloqueado =
    sinEpisodio ||
    nivelSugerido === null ||
    decisionLoading ||
    decisionGuardada ||
    decisionPendiente ||
    !evaluacionReal;

  const motivoValido = motivoManual.trim().length >= MOTIVO_MIN_CARACTERES;
  const cambiaNivel = nivelSugerido !== null && nivelManualActual !== nivelSugerido;

  const seleccionarMotivo = (valor: string) => {
    setTipoMotivo(valor);

    if (valor in MOTIVOS_PREDEFINIDOS) {
      setMotivoManual(
        MOTIVOS_PREDEFINIDOS[valor as keyof typeof MOTIVOS_PREDEFINIDOS],
      );
    } else {
      // "Otro motivo": el texto libre lo escribe la persona.
      setMotivoManual("");
    }
  };

  const cerrarSobrescritura = () => {
    setSobrescribiendo(false);
    setNivelManual(null);
    setTipoMotivo("");
    setMotivoManual("");
  };

  // Confirmar: guarda el nivel sugerido tal cual, sin justificación.
  const confirmar = () => {
    if (nivelSugerido !== null && !bloqueado) {
      onConfirm?.(nivelSugerido, "");
    }
  };

  // Sobrescribir: nivel distinto al sugerido + motivo de al menos 10 caracteres.
  const guardarSobrescritura = () => {
    if (bloqueado || !cambiaNivel || !motivoValido) return;
    onManualDecision?.(nivelManualActual, motivoManual.trim());
  };

  return (
    <div className="bg-white border-4 border-orange-500 p-6 rounded-3xl shadow-lg flex flex-col justify-between h-full min-h-[500px]">
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="bg-slate-800 text-white rounded-lg p-2 font-mono font-bold text-sm tracking-wider shadow">
              Ai
            </div>

            <h3 className="font-bold text-slate-800 text-sm tracking-wide">
              ASISTENTE IA - TriageOps
            </h3>
          </div>

          <button
            type="button"
            onClick={onUpdate}
            disabled={isLoading || sinEpisodio || decisionGuardada}
            className="bg-[#10b981] hover:bg-[#059669] active:scale-95 disabled:opacity-50 text-white font-bold px-5 py-2 rounded-xl text-sm shadow-md transition-all"
          >
            {isLoading ? "Analizando..." : "Actualizar"}
          </button>
        </div>

        <div className="bg-orange-50 border border-orange-100 p-4 rounded-2xl flex flex-col justify-center items-center text-center shadow-inner py-5">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Recomendación:
          </span>

          <span className="text-2xl sm:text-3xl font-extrabold text-orange-600 tracking-tight">
            {esi === null ? "Sin evaluar" : `ESI ${esi} - ${gravedad}`}
          </span>
        </div>

        {!sinEpisodio && !evaluacionReal && !isLoading && (
          <div
            role="status"
            className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-3 text-sm"
          >
            Aún no hay una evaluación clínica para este episodio. Pulse
            Actualizar: cuando exista, podrá confirmar o modificar el nivel ESI.
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-sm"
          >
            {error}
          </div>
        )}

        {avisoFallback && (
          <div
            role="status"
            className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-3 text-sm font-medium"
          >
            {avisoFallback}
          </div>
        )}

        {/* Error al guardar (404, 409, 422 o pérdida de conexión). */}
        {decisionError && (
          <div
            role="alert"
            className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-sm"
          >
            {decisionError}
          </div>
        )}

        {decisionPendiente && (
          <button
            type="button"
            onClick={onRetryDecision}
            disabled={decisionLoading}
            className="w-full bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-bold py-3 rounded-xl"
          >
            {decisionLoading
              ? "Verificando decisión..."
              : "Reintentar guardado"}
          </button>
        )}

        {/* Escenario verde de US-02: decisión guardada y validada por un humano. */}
        {decisionGuardada && decisionResultado && (
          <div
            role="status"
            className="bg-emerald-50 border border-emerald-300 rounded-xl p-3 space-y-1"
          >
            <p className="font-bold text-emerald-800 text-sm">
              ✔ Validado por un humano
            </p>
            <p className="text-xs text-emerald-800">
              {decisionResultado.modificado_manualmente
                ? `Modificado manualmente: ESI ${decisionResultado.nivel_esi_final} (la IA sugirió ESI ${decisionResultado.nivel_esi_sugerido}).`
                : `Confirmado: coincide con la sugerencia de la IA (ESI ${decisionResultado.nivel_esi_final}).`}
            </p>
          </div>
        )}

        {decisionMensaje && (
          <div
            role="status"
            className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl p-3 text-sm"
          >
            {decisionMensaje}
          </div>
        )}

        <div className="space-y-3">
          <h4 className="font-bold text-lg text-slate-800 tracking-tight">
            Justificación:
          </h4>

          <ul className="space-y-2.5 text-sm text-slate-700 font-medium">
            {lineas.length === 0 ? (
              <li className="text-slate-500 font-normal">
                {sinEpisodio
                  ? "Registre el ingreso y pulse Actualizar para obtener la recomendación."
                  : "Pulse Actualizar para obtener la recomendación."}
              </li>
            ) : (
              lineas.map((item, index) => (
                <li
                  key={index}
                  className="flex gap-2.5 items-start leading-relaxed"
                >
                  <span className="text-orange-500 font-bold">•</span>
                  <span>{item}</span>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      <div className="space-y-3 pt-4 border-t border-slate-100">
        {/* Escenario verde: confirmar */}
        <button
          type="button"
          onClick={confirmar}
          disabled={bloqueado || !onConfirm}
          className="disabled:opacity-50 w-full bg-[#10b981] hover:bg-[#059669] text-white font-bold py-3.5 px-4 rounded-xl shadow-md transition-all"
        >
          {decisionLoading
            ? "Guardando decisión..."
            : `Confirmar y asignar ESI ${esi ?? "-"}`}
        </button>

        {/* Escenario amarillo: sobrescribir */}
        {!sobrescribiendo ? (
          <button
            type="button"
            onClick={() => setSobrescribiendo(true)}
            disabled={bloqueado}
            className="disabled:opacity-50 w-full bg-[#ef4444] hover:bg-[#dc2626] text-white font-bold py-3.5 px-4 rounded-xl shadow-md transition-all"
          >
            Sobrescribir nivel manualmente
          </button>
        ) : (
          <div className="space-y-2 border border-red-200 bg-red-50/40 rounded-2xl p-3">
            <label
              htmlFor="nivel-esi-manual"
              className="block text-sm font-semibold text-slate-700"
            >
              Nuevo nivel ESI
            </label>

            <select
              id="nivel-esi-manual"
              value={nivelManualActual}
              onChange={(e) =>
                setNivelManual(Number(e.target.value) as EsiLevel)
              }
              disabled={bloqueado}
              className="w-full border border-slate-300 rounded-xl p-3 bg-white disabled:opacity-50"
            >
              <option value={1}>ESI 1 - Resucitación</option>
              <option value={2}>ESI 2 - Emergencia</option>
              <option value={3}>ESI 3 - Urgencia</option>
              <option value={4}>ESI 4 - Urgencia menor</option>
              <option value={5}>ESI 5 - No urgente</option>
            </select>

            {!cambiaNivel && (
              <p className="text-xs text-amber-700">
                Elija un nivel distinto al sugerido por la IA (ESI {esi}). Para
                mantenerlo, use «Confirmar».
              </p>
            )}

            <label
              htmlFor="tipo-motivo-esi"
              className="block text-sm font-semibold text-slate-700"
            >
              Motivo de modificación
            </label>

            <select
              id="tipo-motivo-esi"
              value={tipoMotivo}
              onChange={(e) => seleccionarMotivo(e.target.value)}
              disabled={bloqueado}
              className="w-full border border-slate-300 rounded-xl p-3 bg-white disabled:opacity-50"
            >
              <option value="">Seleccione un motivo</option>
              <option value="palidez">Palidez observada</option>
              <option value="facies_dolor">Facies de dolor</option>
              <option value="dolor">Dolor intenso</option>
              <option value="deterioro">Deterioro clínico</option>
              <option value="otro">Otro motivo (especificar)</option>
            </select>

            <label
              htmlFor="motivo-esi-manual"
              className="block text-sm font-semibold text-slate-700"
            >
              Justificación clínica
            </label>

            <textarea
              id="motivo-esi-manual"
              value={motivoManual}
              onChange={(e) => setMotivoManual(e.target.value)}
              maxLength={MOTIVO_MAX_CARACTERES}
              rows={3}
              disabled={bloqueado}
              placeholder={`Explique brevemente la decisión clínica (mínimo ${MOTIVO_MIN_CARACTERES} caracteres).`}
              className="w-full border border-slate-300 rounded-xl p-3 text-sm disabled:opacity-50"
            />

            <p
              className={`text-xs ${
                motivoValido ? "text-slate-500" : "text-red-600"
              }`}
            >
              {motivoManual.trim().length}/{MOTIVO_MAX_CARACTERES} caracteres
              (mínimo {MOTIVO_MIN_CARACTERES}).
            </p>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={cerrarSobrescritura}
                disabled={decisionLoading}
                className="flex-1 border border-slate-300 bg-white hover:bg-slate-50 disabled:opacity-50 text-slate-700 font-semibold py-3 rounded-xl"
              >
                Cancelar
              </button>

              <button
                type="button"
                onClick={guardarSobrescritura}
                disabled={
                  bloqueado ||
                  !cambiaNivel ||
                  !motivoValido ||
                  !onManualDecision
                }
                className="flex-1 disabled:opacity-50 bg-[#ef4444] hover:bg-[#dc2626] text-white font-bold py-3 rounded-xl shadow-md transition-all"
              >
                {decisionLoading ? "Guardando..." : "Guardar nivel"}
              </button>
            </div>
          </div>
        )}

        <p className="text-[10px] text-center text-slate-400 italic font-medium leading-normal pt-2">
          Decisión final bajo criterio exclusivo del profesional de enfermería.
        </p>
      </div>
    </div>
  );
};
