"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Navbar } from "@/components/clinical/Navbar";
import { VitalSignsCard } from "@/components/clinical/VitalSignsCard";
import { AIAssistantCard } from "@/components/clinical/AIAssistantCard";
import { PatientLookupCard } from "@/components/clinical/PatientLookupCard";
import { PatientDataCard } from "@/components/clinical/PatientDataCard";
import { AnamnesisPainCard } from "@/components/clinical/AnamnesisPainCard";
import {
  ApiError,
  enviarFormulario,
  type ErrorCampo,
  type FormularioClinicoRespuesta,
  type NivelConciencia,
  type PacienteEncontrado,
} from "@/lib/api";

// Los signos vitales se guardan como texto para distinguir "vacío" de 0.
interface FormState {
  alergias: string;
  nivel_conciencia: NivelConciencia | "";
  presion_sistolica: string;
  presion_diastolica: string;
  frecuencia_cardiaca: string;
  frecuencia_respiratoria: string;
  saturacion_oxigeno: string;
  temperatura: string;
  anamnesis: string;
  escala_dolor: number | null;
}

const FORM_VACIO: FormState = {
  alergias: "",
  nivel_conciencia: "",
  presion_sistolica: "",
  presion_diastolica: "",
  frecuencia_cardiaca: "",
  frecuencia_respiratoria: "",
  saturacion_oxigeno: "",
  temperatura: "",
  anamnesis: "",
  escala_dolor: null,
};

const MAX_MOTIVO = 1000; // límite del backend para motivo_consulta

const aNumero = (texto: string): number => (texto.trim() === "" ? NaN : Number(texto));

export default function NurseTriagePage() {
  const [formData, setFormData] = useState<FormState>(FORM_VACIO);
  const [paciente, setPaciente] = useState<PacienteEncontrado | null>(null);
  const [claveFormulario, setClaveFormulario] = useState(0);

  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [erroresCampo, setErroresCampo] = useState<ErrorCampo[]>([]);
  const [resultado, setResultado] = useState<FormularioClinicoRespuesta | null>(null);

  // Recomendación del asistente IA: sigue siendo una simulación (no hay endpoint de IA todavía).
  const [recommendation, setRecommendation] = useState({
    esi: 3,
    gravedad: "URGENCIA",
    justificacion: ["Complete los datos y pulse Actualizar para ver una recomendación de ejemplo."],
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Borra todo lo que identifica al paciente: formulario, paciente elegido y el buscador.
  // No toca `resultado`, que solo tiene el id del episodio y su estado.
  const limpiarDatosPersonales = useCallback(() => {
    setFormData(FORM_VACIO);
    setPaciente(null);
    setClaveFormulario((k) => k + 1); // vacía el buscador (RUT, nombre y nacimiento)
  }, []);

  // Con el botón "Atrás" el navegador puede restaurar la página tal como estaba (bfcache),
  // con el paciente anterior en pantalla. En ese caso se borra todo.
  useEffect(() => {
    const alMostrar = (e: PageTransitionEvent) => {
      if (!e.persisted) return;
      limpiarDatosPersonales();
      setResultado(null);
      setError(null);
      setErroresCampo([]);
    };
    window.addEventListener("pageshow", alMostrar);
    return () => window.removeEventListener("pageshow", alMostrar);
  }, [limpiarDatosPersonales]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleUpdateTriage = async () => {
    setIsLoading(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 800));
      const fc = aNumero(formData.frecuencia_cardiaca);
      const spo2 = aNumero(formData.saturacion_oxigeno);
      const dolor = formData.escala_dolor ?? 0;

      if (fc < 100 && dolor < 5) {
        setRecommendation({
          esi: 3,
          gravedad: "URGENCIA",
          justificacion: [
            "Signos vitales en rango de estabilidad hemodinámica relativa.",
            "Requiere múltiples recursos diagnósticos complementarios.",
            "Dolor moderado controlado sin signos de compromiso inminente.",
          ],
        });
      } else {
        setRecommendation({
          esi: 2,
          gravedad: "EMERGENCIA",
          justificacion: [
            `Frecuencia Cardíaca en ${fc} bpm con dolor en escala ${dolor}/10.`,
            `Saturación de oxígeno en ${spo2}% requerirá monitoreo activo.`,
            "Se mantiene criterio de alta prioridad por presentación de síntomas.",
          ],
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async () => {
    setError(null);
    setErroresCampo([]);

    if (!paciente) {
      setError("Busque o registre al paciente antes de enviar el formulario.");
      return;
    }
    const nivel = formData.nivel_conciencia;
    if (nivel === "") {
      setError("Seleccione el nivel de conciencia.");
      return;
    }
    if (formData.escala_dolor === null) {
      setError("Seleccione la escala de dolor.");
      return;
    }

    const numeros = {
      presion_sistolica: aNumero(formData.presion_sistolica),
      presion_diastolica: aNumero(formData.presion_diastolica),
      frecuencia_cardiaca: aNumero(formData.frecuencia_cardiaca),
      frecuencia_respiratoria: aNumero(formData.frecuencia_respiratoria),
      temperatura: aNumero(formData.temperatura),
      saturacion_oxigeno: aNumero(formData.saturacion_oxigeno),
    };
    if (Object.values(numeros).some((n) => Number.isNaN(n))) {
      setError("Complete todos los signos vitales.");
      return;
    }

    // El backend no tiene campo de alergias: se incluyen en el motivo de consulta.
    const partes: string[] = [];
    if (formData.anamnesis.trim()) partes.push(formData.anamnesis.trim());
    if (formData.alergias.trim()) partes.push(`Alergias: ${formData.alergias.trim()}`);
    const motivo = partes.join("\n\n");
    if (motivo.length > MAX_MOTIVO) {
      setError(`La anamnesis y las alergias superan los ${MAX_MOTIVO} caracteres (${motivo.length}).`);
      return;
    }

    setEnviando(true);
    try {
      const respuesta = await enviarFormulario({
        patient_id: paciente.patient_id,
        motivo_consulta: motivo || undefined,
        signos_vitales: {
          ...numeros,
          escala_dolor: formData.escala_dolor,
          nivel_conciencia: nivel,
        },
      });
      setResultado(respuesta);
      limpiarDatosPersonales(); // ya quedó guardado en el servidor: no hace falta tenerlo en el navegador
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.errores.length > 0 ? "Revise los datos ingresados:" : e.message);
        setErroresCampo(e.errores);
      } else {
        setError("Error inesperado al enviar el formulario.");
      }
    } finally {
      setEnviando(false);
    }
  };

  const handleNuevoIngreso = () => {
    limpiarDatosPersonales();
    setResultado(null);
    setError(null);
    setErroresCampo([]);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800">
      <Navbar />

      <main className="max-w-[1600px] mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LADO IZQUIERDO: FORMULARIO CLÍNICO (8 columnas) */}
        <section className="lg:col-span-8 space-y-6">
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Ingreso y Evaluación de Triage
          </h1>

          <PatientLookupCard key={claveFormulario} onPacienteChange={setPaciente} />

          <PatientDataCard
            nivel_conciencia={formData.nivel_conciencia}
            alergias={formData.alergias}
            onChange={handleChange}
            onNivelChange={(valor) => setFormData((prev) => ({ ...prev, nivel_conciencia: valor }))}
          />

          <VitalSignsCard
            pas={formData.presion_sistolica}
            pad={formData.presion_diastolica}
            fc={formData.frecuencia_cardiaca}
            fr={formData.frecuencia_respiratoria}
            spo2={formData.saturacion_oxigeno}
            temp={formData.temperatura}
            onChange={handleChange}
          />

          <AnamnesisPainCard
            anamnesis={formData.anamnesis}
            escala_dolor={formData.escala_dolor}
            onChange={handleChange}
            onPainChange={(valor) => setFormData((prev) => ({ ...prev, escala_dolor: valor }))}
          />

          {/* Envío al backend */}
          <div className="space-y-3">
            {error && (
              <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 text-sm">
                <p className="font-bold">{error}</p>
                {erroresCampo.length > 0 && (
                  <ul className="list-disc pl-5 mt-1">
                    {erroresCampo.map((x, i) => (
                      <li key={i}>
                        {x.field.split(".").pop()}: {x.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {resultado ? (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl p-4 text-sm flex items-center justify-between gap-4">
                <p>
                  <span className="font-bold">Ingreso registrado.</span> Episodio{" "}
                  {resultado.episodio_id.slice(0, 8)} — estado: {resultado.estado}.
                </p>
                <button
                  type="button"
                  onClick={handleNuevoIngreso}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-4 py-2 rounded-lg cursor-pointer whitespace-nowrap"
                >
                  Nuevo ingreso
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={enviando}
                className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-bold py-3 rounded-xl cursor-pointer"
              >
                {enviando ? "Registrando..." : "Registrar ingreso a triage"}
              </button>
            )}
          </div>
        </section>

        {/* LADO DERECHO: WIDGET ASISTENTE IA (4 columnas) */}
        <section className="lg:col-span-4 h-full">
          <AIAssistantCard
            esi={recommendation.esi}
            gravedad={recommendation.gravedad}
            justificacion={recommendation.justificacion}
            onUpdate={handleUpdateTriage}
            isLoading={isLoading}
          />
        </section>
      </main>
    </div>
  );
}