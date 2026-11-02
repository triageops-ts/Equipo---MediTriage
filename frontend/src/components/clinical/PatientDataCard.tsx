import React from "react";
import type { NivelConciencia } from "@/lib/api";

interface PatientDataProps {
  nivel_conciencia: NivelConciencia | "";
  alergias: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onNivelChange: (valor: NivelConciencia) => void;
}

const NIVELES: { valor: NivelConciencia; etiqueta: string }[] = [
  { valor: "alerta", etiqueta: "Alerta" },
  { valor: "verbal", etiqueta: "Verbal" },
  { valor: "dolor", etiqueta: "Dolor" },
  { valor: "inconsciente", etiqueta: "Inconsciente" },
];

export const PatientDataCard = ({
  nivel_conciencia,
  alergias,
  onChange,
  onNivelChange,
}: PatientDataProps) => (
  <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4 text-sm">
    <div className="flex items-center gap-4 flex-wrap">
      <span className="font-bold whitespace-nowrap">Nivel de conciencia:</span>
      {NIVELES.map(({ valor, etiqueta }) => (
        <label key={valor} className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="nivel_conciencia"
            checked={nivel_conciencia === valor}
            onChange={() => onNivelChange(valor)}
            className="text-blue-600 focus:ring-0"
          />
          <span>{etiqueta}</span>
        </label>
      ))}
    </div>

    <div className="flex items-center gap-2">
      <label htmlFor="alergias" className="font-bold min-w-[70px]">
        Alergias:
      </label>
      <input
        id="alergias"
        type="text"
        name="alergias"
        value={alergias}
        onChange={onChange}
        className="flex-1 border border-slate-300 rounded px-3 py-1 bg-white focus:outline-none"
      />
    </div>
  </div>
);