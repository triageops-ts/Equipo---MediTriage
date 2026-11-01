import React from "react";

interface VitalSignsProps {
  pa: string;
  fc: number;
  fr: number;
  spo2: number;
  temp: number;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

export const VitalSignsCard = ({ pa, fc, fr, spo2, temp, onChange }: VitalSignsProps) => (
  <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
    <h2 className="flex items-center gap-2 text-md font-bold text-slate-800 border-b pb-2">
      <span className="text-red-500">❤️</span> Signos Vitales
    </h2>

    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      {/* Presión */}
      <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl flex flex-col justify-between h-[100px]">
        <span className="text-[11px] font-semibold text-slate-500 uppercase">Presión Arterial:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="text" name="presion_arterial" value={pa} onChange={onChange} className="w-20 text-center font-bold text-xl bg-transparent focus:outline-none" />
          <span className="text-[10px] text-slate-400">mmHg</span>
        </div>
      </div>

      {/* FC */}
      <div className="bg-red-50/40 border border-red-100 p-3 rounded-xl flex flex-col justify-between h-[100px]">
        <span className="text-[11px] font-semibold text-slate-500 uppercase">Frecuencia Cardíaca:</span>
        <div className="flex flex-col items-center">
          <div className="flex items-baseline justify-center gap-1">
            <input type="number" name="frecuencia_cardiaca" value={fc} onChange={onChange} className="w-14 text-center font-bold text-xl bg-transparent focus:outline-none" />
            <span className="text-[10px] text-slate-400">bpm</span>
          </div>
          {fc > 100 && <span className="text-[9px] text-red-500 font-medium">Alerta de taquicardia</span>}
        </div>
      </div>

      {/* FR */}
      <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl flex flex-col justify-between h-[100px]">
        <span className="text-[11px] font-semibold text-slate-500 uppercase">Frecuencia Respiratoria:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="number" name="frecuencia_respiratoria" value={fr} onChange={onChange} className="w-14 text-center font-bold text-xl bg-transparent focus:outline-none" />
          <span className="text-[10px] text-slate-400">rpm</span>
        </div>
      </div>

      {/* SpO2 */}
      <div className="bg-orange-50/40 border border-orange-100 p-3 rounded-xl flex flex-col justify-between h-[100px]">
        <span className="text-[11px] font-semibold text-slate-500 uppercase">Saturación O2:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="number" name="saturacion_o2" value={spo2} onChange={onChange} className="w-14 text-center font-bold text-xl bg-transparent focus:outline-none" />
          <span className="text-[10px] text-slate-400">%</span>
        </div>
      </div>

      {/* Temperatura */}
      <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl flex flex-col justify-between h-[100px]">
        <span className="text-[11px] font-semibold text-slate-500 uppercase">Temperatura:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="number" step="0.1" name="temperatura" value={temp} onChange={onChange} className="w-16 text-center font-bold text-xl bg-transparent focus:outline-none" />
          <span className="text-[10px] text-slate-400">°C</span>
        </div>
      </div>
    </div>
  </div>
);