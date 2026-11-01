import React from "react";

interface AIAssistantProps {
  esi: number;
  gravedad: string;
  justificacion: string[];
  onUpdate?: () => void;
  isLoading?: boolean;
}

export const AIAssistantCard = ({
  esi,
  gravedad,
  justificacion,
  onUpdate,
  isLoading = false,
}: AIAssistantProps) => (
  <div className="bg-white border-4 border-orange-500 p-6 rounded-3xl shadow-lg flex flex-col justify-between h-full min-h-[500px]">
    <div className="space-y-6">
      {/* Cabecera con Asistente y Botón Actualizar */}
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
          disabled={isLoading}
          className="bg-[#10b981] hover:bg-[#059669] active:scale-95 disabled:opacity-50 text-white font-bold px-5 py-2 rounded-xl text-sm shadow-md transition-all cursor-pointer"
        >
          {isLoading ? "Analizando..." : "Actualizar"}
        </button>
      </div>

      {/* Recomendación principal de nivel ESI */}
      <div className="bg-orange-50 border border-orange-100 p-4 rounded-2xl flex flex-col justify-center items-center text-center shadow-inner py-5">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Recomendación:
        </span>
        <span className="text-2xl sm:text-3xl font-extrabold text-orange-600 tracking-tight">
          ESI {esi} - {gravedad}
        </span>
      </div>

      {/* Justificación Médica */}
      <div className="space-y-3">
        <h4 className="font-bold text-lg text-slate-800 tracking-tight">
          Justificación:
        </h4>
        <ul className="space-y-2.5 text-sm text-slate-700 font-medium">
          {justificacion.map((item, index) => (
            <li key={index} className="flex gap-2.5 items-start leading-relaxed">
              <span className="text-orange-500 font-bold">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>

    {/* Botones inferiores */}
    <div className="space-y-3 pt-4 border-t border-slate-100">
      <button
        onClick={() => alert(`ESI ${esi} confirmado.`)}
        className="w-full bg-[#10b981] hover:bg-[#059669] text-white font-bold py-3.5 px-4 rounded-xl shadow-md transition-all active:scale-[0.98]"
      >
        Confirmar y Asignar ESI {esi}
      </button>

      <button
        onClick={() => alert("Sobrescritura manual")}
        className="w-full bg-[#ef4444] hover:bg-[#dc2626] text-white font-bold py-3.5 px-4 rounded-xl shadow-md transition-all active:scale-[0.98]"
      >
        Sobrescribir Nivel Manualmente
      </button>

      <p className="text-[10px] text-center text-slate-400 italic font-medium leading-normal pt-2">
        Decisión final bajo criterio exclusivo del profesional de enfermería.
      </p>
    </div>
  </div>
);