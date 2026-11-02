import React from "react";

// Los valores llegan como texto para poder distinguir "vacío" de 0.
interface VitalSignsProps {
  pas: string;
  pad: string;
  fc: string;
  fr: string;
  spo2: string;
  temp: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const CAJA = "p-3 rounded-xl flex flex-col justify-between h-[100px]";
const VALOR = "text-center font-bold text-xl bg-transparent focus:outline-none";
const ETIQUETA = "text-[11px] font-semibold text-slate-500 uppercase";
const UNIDAD = "text-[10px] text-slate-400";

export const VitalSignsCard = ({ pas, pad, fc, fr, spo2, temp, onChange }: VitalSignsProps) => (
  <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
    <h2 className="flex items-center gap-2 text-md font-bold text-slate-800 border-b pb-2">
      <span className="text-red-500">❤️</span> Signos Vitales
    </h2>

    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      {/* Presión arterial: sistólica / diastólica */}
      <div className={`bg-slate-50 border border-slate-200 ${CAJA}`}>
        <span className={ETIQUETA}>Presión Arterial:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="number" name="presion_sistolica" value={pas} onChange={onChange} placeholder="120" className={`w-14 ${VALOR}`} />
          <span className="text-slate-400">/</span>
          <input type="number" name="presion_diastolica" value={pad} onChange={onChange} placeholder="80" className={`w-14 ${VALOR}`} />
          <span className={UNIDAD}>mmHg</span>
        </div>
      </div>

      {/* FC */}
      <div className={`bg-red-50/40 border border-red-100 ${CAJA}`}>
        <span className={ETIQUETA}>Frecuencia Cardíaca:</span>
        <div className="flex flex-col items-center">
          <div className="flex items-baseline justify-center gap-1">
            <input type="number" name="frecuencia_cardiaca" value={fc} onChange={onChange} placeholder="80" className={`w-14 ${VALOR}`} />
            <span className={UNIDAD}>bpm</span>
          </div>
          {Number(fc) > 100 && <span className="text-[9px] text-red-500 font-medium">Alerta de taquicardia</span>}
        </div>
      </div>

      {/* FR */}
      <div className={`bg-slate-50 border border-slate-200 ${CAJA}`}>
        <span className={ETIQUETA}>Frecuencia Respiratoria:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="number" name="frecuencia_respiratoria" value={fr} onChange={onChange} placeholder="16" className={`w-14 ${VALOR}`} />
          <span className={UNIDAD}>rpm</span>
        </div>
      </div>

      {/* SpO2 */}
      <div className={`bg-orange-50/40 border border-orange-100 ${CAJA}`}>
        <span className={ETIQUETA}>Saturación O2:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="number" name="saturacion_oxigeno" value={spo2} onChange={onChange} placeholder="98" className={`w-14 ${VALOR}`} />
          <span className={UNIDAD}>%</span>
        </div>
      </div>

      {/* Temperatura */}
      <div className={`bg-slate-50 border border-slate-200 ${CAJA}`}>
        <span className={ETIQUETA}>Temperatura:</span>
        <div className="flex items-baseline justify-center gap-1">
          <input type="number" step="0.1" name="temperatura" value={temp} onChange={onChange} placeholder="36.5" className={`w-16 ${VALOR}`} />
          <span className={UNIDAD}>°C</span>
        </div>
      </div>
    </div>
  </div>
);