import React from "react";

interface PatientDataProps {
  rut: string;
  nombre: string;
  alergias: string;
  edad: number;
  hora_llegada: string;
  sexo: string;
  nivel_conciencia: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRadioChange: (field: string, value: string) => void;
}

export const PatientDataCard = ({
  rut,
  nombre,
  alergias,
  edad,
  hora_llegada,
  sexo,
  nivel_conciencia,
  onChange,
  onRadioChange,
}: PatientDataProps) => (
  <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center text-sm">
      <div className="md:col-span-4 flex items-center gap-2">
        <label className="font-bold min-w-[70px]">RUT/ID:</label>
        <input type="text" name="rut" value={rut} onChange={onChange} className="flex-1 border border-slate-300 rounded px-3 py-1 bg-white focus:outline-none" />
      </div>

      <div className="md:col-span-3 flex items-center gap-2">
        <label className="font-bold min-w-[45px]">Edad:</label>
        <input type="number" name="edad" value={edad} onChange={onChange} className="flex-1 max-w-[80px] text-center border border-slate-300 rounded px-2 py-1 bg-white focus:outline-none" />
      </div>

      <div className="md:col-span-5 flex items-center gap-4">
        <span className="font-bold">Sexo:</span>
        {["Masculino", "Femenino"].map((opt) => (
          <label key={opt} className="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" name="sexo" checked={sexo === opt} onChange={() => onRadioChange("sexo", opt)} className="text-blue-600 focus:ring-0" />
            <span>{opt}</span>
          </label>
        ))}
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center text-sm">
      <div className="md:col-span-4 flex items-center gap-2">
        <label className="font-bold min-w-[70px]">Nombre:</label>
        <input type="text" name="nombre" value={nombre} onChange={onChange} className="flex-1 border border-slate-300 rounded px-3 py-1 bg-white focus:outline-none" />
      </div>

      <div className="md:col-span-3 flex items-center gap-2">
        <label className="font-bold min-w-[45px] leading-tight">Hora de llegada:</label>
        <input type="text" name="hora_llegada" value={hora_llegada} onChange={onChange} className="flex-1 max-w-[80px] text-center border border-slate-300 rounded px-2 py-1 bg-white focus:outline-none" />
      </div>

      <div className="md:col-span-5 flex items-center gap-4 flex-wrap">
        <span className="font-bold whitespace-nowrap">Nivel de conciencia:</span>
        {["Alerta", "Dolor", "Verbal", "Inconciente"].map((opt) => (
          <label key={opt} className="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" name="nivel_conciencia" checked={nivel_conciencia === opt} onChange={() => onRadioChange("nivel_conciencia", opt)} className="text-blue-600 focus:ring-0" />
            <span>{opt}</span>
          </label>
        ))}
      </div>
    </div>

    <div className="flex items-center gap-2 text-sm">
      <label className="font-bold min-w-[70px]">Alergias:</label>
      <input type="text" name="alergias" value={alergias} onChange={onChange} className="flex-1 border border-slate-300 rounded px-3 py-1 bg-white focus:outline-none" />
    </div>
  </div>
);