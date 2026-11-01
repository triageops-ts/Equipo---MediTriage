import React from "react";

interface AnamnesisPainProps {
  anamnesis: string;
  escala_dolor: number;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onPainChange: (value: number) => void;
}

export const AnamnesisPainCard = ({
  anamnesis,
  escala_dolor,
  onChange,
  onPainChange,
}: AnamnesisPainProps) => (
  <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
    <h2 className="text-md font-bold text-slate-800 border-b pb-2">
      Anamnesis y Escala de Dolor
    </h2>

    <textarea
      name="anamnesis"
      value={anamnesis}
      onChange={onChange}
      rows={5}
      className="w-full text-sm border border-slate-200 rounded-lg p-3 bg-white text-slate-700 leading-relaxed focus:outline-none"
    />

    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-2">
      <span className="font-bold text-sm min-w-[120px]">
        Escala de Dolor:
      </span>
      <div className="flex-1 grid grid-cols-10 gap-1.5 max-w-[650px]">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => {
          const isSelected = escala_dolor === num;
          return (
            <button
              key={num}
              type="button"
              onClick={() => onPainChange(num)}
              className={`flex flex-col items-center gap-1 p-1 rounded transition-all ${
                isSelected
                  ? "bg-orange-500 text-white font-bold transform scale-110 shadow-md"
                  : "bg-slate-50 border border-slate-200 hover:bg-slate-100 text-slate-600"
              }`}
            >
              <span
                className={`w-full h-1.5 rounded-full ${
                  isSelected ? "bg-white" : "bg-orange-300"
                }`}
              />
              <span className="text-xs">{num}</span>
            </button>
          );
        })}
      </div>
    </div>
  </div>
);