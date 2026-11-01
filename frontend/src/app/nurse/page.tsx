"use client";

import React, { useState } from "react";
import { Navbar } from "@/components/clinical/Navbar";
import { VitalSignsCard } from "@/components/clinical/VitalSignsCard";
import { AIAssistantCard } from "@/components/clinical/AIAssistantCard";
import { PatientDataCard } from "@/components/clinical/PatientDataCard";
import { AnamnesisPainCard } from "@/components/clinical/AnamnesisPainCard";

interface ClinicalFormData {
  rut: string;
  nombre: string;
  alergias: string;
  edad: number;
  hora_llegada: string;
  sexo: string;
  nivel_conciencia: string;
  presion_arterial: string;
  frecuencia_cardiaca: number;
  frecuencia_respiratoria: number;
  saturacion_o2: number;
  temperatura: number;
  anamnesis: string;
  escala_dolor: number;
}

export default function NurseTriagePage() {
  const [formData, setFormData] = useState<ClinicalFormData>({
    rut: "11.111.111-1",
    nombre: "Juan Carlos Pérez",
    alergias: "Lorem Ipsum es simplemente el texto de relleno de las imprentas y archivos.",
    edad: 20,
    hora_llegada: "18:35",
    sexo: "Masculino",
    nivel_conciencia: "Alerta",
    presion_arterial: "145/95",
    frecuencia_cardiaca: 112,
    frecuencia_respiratoria: 22,
    saturacion_o2: 91,
    temperatura: 37.2,
    anamnesis:
      "Lorem Ipsum es simplemente el texto de relleno de las imprentas y archivos de texto. Lorem Ipsum ha sido el texto de relleno estándar de las industrias desde el año 1500, cuando un impresor (N. del T. persona que se dedica a la imprenta) desconocido usó una galería de textos y los mezcló de tal manera que logró hacer un libro de textos especímen. No sólo sobrevivió 500 años, sino que también ingresó como texto de relleno en documentos electrónicos, quedando esencialmente igual al original. Fue popularizado en los 60s con la creación de las hojas 'Letraset', las cuales contenían pasajes de Lorem Ipsum, y más recientemente con software de autoedición, como por ejemplo Aldus PageMaker, el cual incluye versiones de Lorem Ipsum.",
    escala_dolor: 8,
  });

  const [recommendation, setRecommendation] = useState({
    esi: 2,
    gravedad: "EMERGENCIA",
    justificacion: [
      "Taquicardia sinusal (112 bpm) asociada a dolor torácico opresivo de inicio súbito y diaforesis.",
      "Desaturación leve (91% SpO2) y taquípnea.",
      "Alto riesgo de síndrome coronario agudo.",
    ],
  });

  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Manejador para inputs de texto y numéricos (incluye textarea)
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: e.target.type === "number" ? Number(value) : value,
    }));
  };

  // Manejador especial para botones de radio y escala de dolor
  const handleCustomFieldChange = (field: keyof ClinicalFormData, value: string | number) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleUpdateTriage = async () => {
    setIsLoading(true);
    console.log("Enviando datos clínicos para reclasificación:", formData);

    try {
      await new Promise((resolve) => setTimeout(resolve, 800));

      if (formData.frecuencia_cardiaca < 100 && formData.escala_dolor < 5) {
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
            `Frecuencia Cardíaca en ${formData.frecuencia_cardiaca} bpm con dolor en escala ${formData.escala_dolor}/10.`,
            `Saturación de oxígeno en ${formData.saturacion_o2}% requerirá monitoreo activo.`,
            "Se mantiene criterio de alta prioridad por presentación de síntomas.",
          ],
        });
      }
    } catch (error) {
      console.error("Error al actualizar triage:", error);
    } finally {
      setIsLoading(false);
    }
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

          <PatientDataCard
            rut={formData.rut}
            nombre={formData.nombre}
            alergias={formData.alergias}
            edad={formData.edad}
            hora_llegada={formData.hora_llegada}
            sexo={formData.sexo}
            nivel_conciencia={formData.nivel_conciencia}
            onChange={handleChange}
            onRadioChange={handleCustomFieldChange}
          />

          <VitalSignsCard
            pa={formData.presion_arterial}
            fc={formData.frecuencia_cardiaca}
            fr={formData.frecuencia_respiratoria}
            spo2={formData.saturacion_o2}
            temp={formData.temperatura}
            onChange={handleChange}
          />

          <AnamnesisPainCard
            anamnesis={formData.anamnesis}
            escala_dolor={formData.escala_dolor}
            onChange={handleChange}
            onPainChange={(value) => handleCustomFieldChange("escala_dolor", value)}
          />
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