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
  evaluarTriage,
  registrarDecision,
  registrarFalloDecision,
  obtenerDecision,
  type ClasificacionIA,
  type DecisionInput,
  type DecisionResponse,
  type ErrorCampo,
  type FormularioClinicoRespuesta,
  type NivelConciencia,
  type PacienteEncontrado,
  type SeveridadSintoma,
  type EsiLevel,
} from "@/lib/api";

interface SintomaForm {
  codigo_sintoma: string;
  severidad: SeveridadSintoma;
  tiempo_evolucion_horas: string;
}

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
  sintomas: SintomaForm[];
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
  sintomas: [],
};

const MAX_MOTIVO = 1000;

const aNumero = (texto: string): number =>
  texto.trim() === "" ? NaN : Number(texto);

export default function NurseTriagePage() {
  const [formData, setFormData] = useState<FormState>(FORM_VACIO);
  const [paciente, setPaciente] = useState<PacienteEncontrado | null>(null);
  const [claveFormulario, setClaveFormulario] = useState(0);

  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [erroresCampo, setErroresCampo] = useState<ErrorCampo[]>([]);
  const [resultado, setResultado] =
    useState<FormularioClinicoRespuesta | null>(null);

  const [recommendation, setRecommendation] = useState<{
    esi: EsiLevel | null;
    gravedad: string;
    justificacion: string[];
  }>({
    esi: null,
    gravedad: "",
    justificacion: [
      "Registre el ingreso y pulse Actualizar para solicitar la evaluación.",
    ],
  });

  const [clasificacion, setClasificacion] =
    useState<ClasificacionIA | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionGuardada, setDecisionGuardada] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decisionMensaje, setDecisionMensaje] = useState<string | null>(null);
  const [decisionPendiente, setDecisionPendiente] =
    useState<DecisionInput | null>(null);

  const limpiarEstadoDecision = useCallback(() => {
    setDecisionLoading(false);
    setDecisionGuardada(false);
    setDecisionError(null);
    setDecisionMensaje(null);
    setDecisionPendiente(null);
  }, []);

  const limpiarDatosPersonales = useCallback(() => {
    setFormData(FORM_VACIO);
    setPaciente(null);
    setClaveFormulario((k) => k + 1);
  }, []);

  useEffect(() => {
    const alMostrar = (e: PageTransitionEvent) => {
      if (!e.persisted) return;

      limpiarDatosPersonales();
      limpiarEstadoDecision();
      setResultado(null);
      setError(null);
      setErroresCampo([]);
    };

    window.addEventListener("pageshow", alMostrar);

    return () => window.removeEventListener("pageshow", alMostrar);
  }, [limpiarDatosPersonales, limpiarEstadoDecision]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const agregarSintoma = () => {
    setFormData((prev) => ({
      ...prev,
      sintomas: [
        ...prev.sintomas,
        {
          codigo_sintoma: "",
          severidad: "leve",
          tiempo_evolucion_horas: "",
        },
      ],
    }));
  };

  const actualizarSintoma = (
    index: number,
    campo: keyof SintomaForm,
    valor: string
  ) => {
    setFormData((prev) => ({
      ...prev,
      sintomas: prev.sintomas.map((sintoma, i) =>
        i === index ? { ...sintoma, [campo]: valor } : sintoma
      ),
    }));
  };

  const eliminarSintoma = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      sintomas: prev.sintomas.filter((_, i) => i !== index),
    }));
  };

  const handleUpdateTriage = async () => {
    const episodioId = resultado?.episodio_id;

    if (!episodioId || isLoading || decisionGuardada) {
      setError("Primero registre el ingreso clínico del paciente.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setClasificacion(null);
    setRecommendation({
      esi: null,
      gravedad: "",
      justificacion: ["Solicitando evaluación al servicio clínico..."],
    });

    try {
      const evaluacion = await evaluarTriage(episodioId);

      if (evaluacion.episodio_id !== episodioId) {
        throw new Error(
          "La evaluación recibida no corresponde al episodio actual."
        );
      }

      setClasificacion(evaluacion);

      const nivel = evaluacion.nivel_esi_sugerido;
      const gravedadPorNivel: Record<EsiLevel, string> = {
        1: "RESUCITACIÓN",
        2: "EMERGENCIA",
        3: "URGENCIA",
        4: "URGENCIA MENOR",
        5: "NO URGENTE",
      };

      setRecommendation({
        esi: nivel,
        gravedad: gravedadPorNivel[nivel],
        justificacion: evaluacion.justificacion_ia
          .split("\n")
          .map((linea) => linea.trim())
          .filter(Boolean),
      });
    } catch (e: unknown) {
      setClasificacion(null);
      setRecommendation({
        esi: null,
        gravedad: "",
        justificacion: [
          "No se obtuvo una evaluación válida. Puede volver a intentarlo.",
        ],
      });

      setError(
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "No se pudo realizar la evaluación clínica."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const aplicarDecisionGuardada = (decision: DecisionResponse) => {
    setDecisionGuardada(true);
    setDecisionPendiente(null);
    setDecisionError(null);

    setDecisionMensaje(
      decision.modificado_manualmente
        ? `Decisión guardada: ESI ${decision.nivel_esi_final}. Motivo registrado.`
        : `Decisión confirmada y guardada: ESI ${decision.nivel_esi_final}.`
    );
  };

  const verificarDecision = async (
    id: string,
    pendiente: DecisionInput
  ): Promise<"guardada" | "no_guardada" | "error" | "conflicto"> => {
    try {
      const existente = await obtenerDecision(id);

      const coincide =
        existente.episodio_id === id &&
        existente.nivel_esi_final === pendiente.nivel_esi_final &&
        (existente.justificacion ?? "").trim() ===
          (pendiente.justificacion ?? "").trim();

      if (coincide) {
        aplicarDecisionGuardada(existente);
        return "guardada";
      }

      setDecisionError(
        "El episodio ya tiene una decisión registrada diferente. No se volverá a enviar."
      );
      setDecisionPendiente(null);

      return "conflicto";
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        return "no_guardada";
      }

      return "error";
    }
  };

  const handleGuardarDecision = async (
    nivel: EsiLevel,
    justificacion: string
  ) => {
    const id = resultado?.episodio_id;
    const evaluacion = clasificacion;

    if (!id || !evaluacion || evaluacion.episodio_id !== id) {
      setDecisionError(
        "Debe obtener una evaluación clínica válida antes de registrar la decisión."
      );
      return;
    }

    if (decisionLoading || decisionGuardada) return;

    const cambiaNivel = nivel !== evaluacion.nivel_esi_sugerido;
    const motivo = justificacion.trim();

    if (cambiaNivel && motivo.length < 10) {
      setDecisionError(
        "La modificación del nivel ESI requiere una justificación de al menos 10 caracteres."
      );
      return;
    }

    const pendiente: DecisionInput = {
      nivel_esi_final: nivel,
      ...(cambiaNivel ? { justificacion: motivo } : {}),
    };

    setDecisionPendiente(pendiente);
    setDecisionError(null);
    setDecisionMensaje(null);
    setDecisionLoading(true);

    try {
      const respuesta = await registrarDecision(id, pendiente);
      aplicarDecisionGuardada(respuesta);
    } catch (e: unknown) {
      const estado = await verificarDecision(id, pendiente);

      if (estado === "guardada" || estado === "conflicto") {
        return;
      }

      if (estado === "no_guardada") {
        try {
          await registrarFalloDecision(id, pendiente);
        } catch {
          // La auditoría no debe impedir mostrar el error ni ofrecer reintento.
        }

        setDecisionError(
          e instanceof ApiError
            ? e.message
            : "No se pudo confirmar el guardado. Use Reintentar guardado."
        );
      } else {
        setDecisionError(
          "No se pudo verificar si la decisión quedó registrada. Use Reintentar guardado antes de volver a enviarla."
        );
      }
    } finally {
      setDecisionLoading(false);
    }
  };

  const handleReintentarDecision = async () => {
    const id = resultado?.episodio_id;
    const pendiente = decisionPendiente;

    if (!id || !pendiente || decisionLoading || decisionGuardada) {
      return;
    }

    const episodioId = id;

    setDecisionLoading(true);
    setDecisionError(null);
    setDecisionMensaje(null);

    try {
      const estado = await verificarDecision(episodioId, pendiente);

      if (estado === "guardada" || estado === "conflicto") {
        return;
      }

      if (estado === "error") {
        setDecisionError(
          "No se pudo verificar si la decisión quedó guardada. No se repetirá el envío para evitar duplicados."
        );
        return;
      }

      const respuesta = await registrarDecision(episodioId, pendiente);
      aplicarDecisionGuardada(respuesta);
    } catch (e: unknown) {
      const estado = await verificarDecision(episodioId, pendiente);

      if (estado === "no_guardada") {
        try {
          await registrarFalloDecision(episodioId, pendiente);
        } catch {
          // La auditoría no debe bloquear el flujo de reintento.
        }
      }

      if (estado !== "guardada" && estado !== "conflicto") {
        setDecisionError(
          e instanceof ApiError
            ? e.message
            : e instanceof Error
              ? e.message
              : "No se pudo guardar la decisión. Intente nuevamente."
        );
      }
    } finally {
      setDecisionLoading(false);
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

    if (Object.values(numeros).some((n) => !Number.isFinite(n))) {
      setError("Complete todos los signos vitales con valores numéricos.");
      return;
    }

    for (let i = 0; i < formData.sintomas.length; i++) {
      const sintoma = formData.sintomas[i];

      if (!sintoma.codigo_sintoma.trim()) {
        setError(`Ingrese el código del síntoma ${i + 1}.`);
        return;
      }

      if (
        sintoma.tiempo_evolucion_horas.trim() !== "" &&
        (!Number.isInteger(Number(sintoma.tiempo_evolucion_horas)) ||
          Number(sintoma.tiempo_evolucion_horas) < 0)
      ) {
        setError(
          `El tiempo de evolución del síntoma ${i + 1} debe ser un número entero mayor o igual a cero.`
        );
        return;
      }
    }

    const partes: string[] = [];

    if (formData.anamnesis.trim()) {
      partes.push(formData.anamnesis.trim());
    }

    if (formData.alergias.trim()) {
      partes.push(`Alergias: ${formData.alergias.trim()}`);
    }

    const motivo = partes.join("\n\n");

    if (motivo.length > MAX_MOTIVO) {
      setError(
        `La anamnesis y las alergias superan los ${MAX_MOTIVO} caracteres (${motivo.length}).`
      );
      return;
    }

    const sintomas = formData.sintomas.map((sintoma) => ({
      codigo_sintoma: sintoma.codigo_sintoma.trim(),
      severidad: sintoma.severidad,
      ...(sintoma.tiempo_evolucion_horas.trim() !== ""
        ? {
            tiempo_evolucion_horas: Number(
              sintoma.tiempo_evolucion_horas
            ),
          }
        : {}),
    }));

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
        sintomas,
      });

      setResultado(respuesta);
      setClasificacion(null);
      setRecommendation({
        esi: null,
        gravedad: "",
        justificacion: [
          "Ingreso registrado. Pulse Actualizar para solicitar la evaluación clínica.",
        ],
      });

      limpiarEstadoDecision();
      limpiarDatosPersonales();
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        setError(
          e.errores.length > 0
            ? "Revise los datos ingresados:"
            : e.message
        );
        setErroresCampo(e.errores);
      } else {
        setError(
          e instanceof Error
            ? e.message
            : "Error inesperado al enviar el formulario."
        );
      }
    } finally {
      setEnviando(false);
    }
  };

  const handleNuevoIngreso = () => {
    limpiarDatosPersonales();
    limpiarEstadoDecision();
    setResultado(null);
    setClasificacion(null);

    setRecommendation({
      esi: null,
      gravedad: "",
      justificacion: ["Registre un ingreso para comenzar."],
    });

    setError(null);
    setErroresCampo([]);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800">
      <Navbar />

      <main className="max-w-[1600px] mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        <section className="lg:col-span-8 space-y-6">
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Ingreso y Evaluación de Triage
          </h1>

          <PatientLookupCard
            key={claveFormulario}
            onPacienteChange={setPaciente}
          />

          <PatientDataCard
            nivel_conciencia={formData.nivel_conciencia}
            alergias={formData.alergias}
            onChange={handleChange}
            onNivelChange={(valor) =>
              setFormData((prev) => ({
                ...prev,
                nivel_conciencia: valor,
              }))
            }
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
            onPainChange={(valor) =>
              setFormData((prev) => ({
                ...prev,
                escala_dolor: valor,
              }))
            }
          />

          <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-slate-800">
                  Síntomas del paciente
                </h2>
                <p className="text-sm text-slate-500">
                  Registre los síntomas identificados durante la evaluación.
                </p>
              </div>

              <button
                type="button"
                onClick={agregarSintoma}
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg"
              >
                + Agregar síntoma
              </button>
            </div>

            {formData.sintomas.length === 0 ? (
              <p className="text-sm text-slate-500 bg-slate-50 rounded-lg p-4">
                No se han agregado síntomas. Puede añadir uno o varios.
              </p>
            ) : (
              <div className="space-y-4">
                {formData.sintomas.map((sintoma, index) => (
                  <div
                    key={index}
                    className="border border-slate-200 rounded-lg p-4 space-y-3"
                  >
                    <div className="flex justify-between items-center">
                      <h3 className="font-semibold text-slate-700">
                        Síntoma {index + 1}
                      </h3>

                      <button
                        type="button"
                        onClick={() => eliminarSintoma(index)}
                        className="text-red-600 hover:text-red-800 text-sm font-medium"
                      >
                        Eliminar
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label
                          htmlFor={`codigo-sintoma-${index}`}
                          className="block text-sm font-medium mb-1"
                        >
                          Código del síntoma
                        </label>

                        <input
                          id={`codigo-sintoma-${index}`}
                          type="text"
                          value={sintoma.codigo_sintoma}
                          onChange={(e) =>
                            actualizarSintoma(
                              index,
                              "codigo_sintoma",
                              e.target.value
                            )
                          }
                          placeholder="Ej. DOLOR_CABEZA"
                          className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                        />
                      </div>

                      <div>
                        <label
                          htmlFor={`severidad-${index}`}
                          className="block text-sm font-medium mb-1"
                        >
                          Severidad
                        </label>

                        <select
                          id={`severidad-${index}`}
                          value={sintoma.severidad}
                          onChange={(e) =>
                            actualizarSintoma(
                              index,
                              "severidad",
                              e.target.value
                            )
                          }
                          className="w-full border border-slate-300 rounded-lg p-2 text-sm bg-white"
                        >
                          <option value="leve">Leve</option>
                          <option value="moderada">Moderada</option>
                          <option value="severa">Severa</option>
                        </select>
                      </div>

                      <div>
                        <label
                          htmlFor={`evolucion-${index}`}
                          className="block text-sm font-medium mb-1"
                        >
                          Evolución (horas)
                        </label>

                        <input
                          id={`evolucion-${index}`}
                          type="number"
                          min="0"
                          step="1"
                          value={sintoma.tiempo_evolucion_horas}
                          onChange={(e) =>
                            actualizarSintoma(
                              index,
                              "tiempo_evolucion_horas",
                              e.target.value
                            )
                          }
                          placeholder="Opcional"
                          className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <div className="space-y-3">
            {error && (
              <div
                role="alert"
                className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 text-sm"
              >
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
                  <span className="font-bold">Ingreso registrado.</span>{" "}
                  Episodio {resultado.episodio_id.slice(0, 8)} — estado:{" "}
                  {resultado.estado}.
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

        <section className="lg:col-span-4 h-full">
          <AIAssistantCard
            key={
              clasificacion?.clasificacion_id ??
              resultado?.episodio_id ??
              "sin-episodio"
            }
            esi={recommendation.esi}
            evaluacionReal={Boolean(
              clasificacion &&
                clasificacion.episodio_id === resultado?.episodio_id
            )}
            avisoFallback={
              clasificacion?.fallback_aplicado
                ? "La IA no estuvo disponible. Se utilizó el mecanismo de respaldo basado en reglas; esta evaluación no fue generada por el modelo de IA."
                : null
            }
            error={error}
            gravedad={recommendation.gravedad}
            justificacion={recommendation.justificacion.join(" ")}
            onUpdate={handleUpdateTriage}
            isLoading={isLoading}
            sinEpisodio={!resultado?.episodio_id}
            onConfirm={handleGuardarDecision}
            onManualDecision={handleGuardarDecision}
            onRetryDecision={handleReintentarDecision}
            decisionLoading={decisionLoading}
            decisionGuardada={decisionGuardada}
            decisionError={decisionError}
            decisionMensaje={decisionMensaje}
            decisionPendiente={decisionPendiente !== null}
          />
        </section>
      </main>
    </div>
  );
}
