"use client";

import React, { useState } from "react";
import {
  ApiError,
  buscarPaciente,
  crearPaciente,
  type PacienteEncontrado,
  type SexoBiologico,
} from "@/lib/api";

type Estado = "inicial" | "buscando" | "encontrado" | "nuevo" | "registrando";

interface PatientLookupProps {
  /** Se llama con el paciente listo para el triage, o con null si no hay uno. */
  onPacienteChange: (paciente: PacienteEncontrado | null) => void;
}

function calcularEdad(fechaIso: string | null): string {
  if (!fechaIso) return "—";
  const [anio, mes, dia] = fechaIso.split("-").map(Number);
  const hoy = new Date();
  let edad = hoy.getFullYear() - anio;
  const mesHoy = hoy.getMonth() + 1;
  if (mesHoy < mes || (mesHoy === mes && hoy.getDate() < dia)) edad -= 1;
  return `${edad} años`;
}

const ETIQUETA_SEXO: Record<SexoBiologico, string> = {
  male: "Masculino",
  female: "Femenino",
};

const INPUT =
  "flex-1 border border-slate-300 rounded px-3 py-1 bg-white focus:outline-none";

export const PatientLookupCard = ({ onPacienteChange }: PatientLookupProps) => {
  const [rut, setRut] = useState("");
  const [estado, setEstado] = useState<Estado>("inicial");
  const [paciente, setPaciente] = useState<PacienteEncontrado | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Datos para registrar un paciente nuevo
  const [nombre, setNombre] = useState("");
  const [fechaNacimiento, setFechaNacimiento] = useState("");
  const [sexo, setSexo] = useState<SexoBiologico | "">("");
  const [consentimiento, setConsentimiento] = useState(false);

  const reiniciar = () => {
    setEstado("inicial");
    setPaciente(null);
    setError(null);
    setNombre("");
    setFechaNacimiento("");
    setSexo("");
    setConsentimiento(false);
    onPacienteChange(null);
  };

  const handleRutChange = (valor: string) => {
    setRut(valor);
    if (estado !== "inicial") reiniciar();
  };

  const handleBuscar = async () => {
    if (!rut.trim()) {
      setError("Ingrese un RUT para buscar.");
      return;
    }
    setError(null);
    setEstado("buscando");
    try {
      const resultado = await buscarPaciente(rut);
      if (resultado.length > 0) {
        setPaciente(resultado[0]);
        setEstado("encontrado");
        onPacienteChange(resultado[0]);
      } else {
        setEstado("nuevo");
        onPacienteChange(null);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Error inesperado al buscar.");
      setEstado("inicial");
    }
  };

  const handleRegistrar = async () => {
    setError(null);
    setEstado("registrando");
    try {
      const creado = await crearPaciente({
        rut,
        name: nombre,
        birth_date: fechaNacimiento || undefined,
        biological_sex: sexo || undefined,
        has_consent: consentimiento,
      });
      setPaciente(creado);
      setEstado("encontrado");
      onPacienteChange(creado);
    } catch (e) {
      if (e instanceof ApiError) {
        const detalle = e.errores.map((x) => x.message).join(" ");
        setError(detalle || e.message);
      } else {
        setError("Error inesperado al registrar.");
      }
      setEstado("nuevo");
    }
  };

  const ocupado = estado === "buscando" || estado === "registrando";

  return (
    <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4 text-sm">
      <h2 className="text-md font-bold text-slate-800 border-b pb-2">Paciente</h2>

      <div className="flex items-center gap-2">
        <label htmlFor="rut" className="font-bold min-w-[70px]">
          RUT/ID:
        </label>
        <input
          id="rut"
          type="text"
          value={rut}
          placeholder="12.345.678-5"
          onChange={(e) => handleRutChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleBuscar();
          }}
          className={INPUT}
        />
        <button
          type="button"
          onClick={handleBuscar}
          disabled={ocupado}
          className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-bold px-4 py-1.5 rounded-lg cursor-pointer"
        >
          {estado === "buscando" ? "Buscando..." : "Buscar"}
        </button>
      </div>

      {error && (
        <p role="alert" className="text-red-600 font-medium">
          {error}
        </p>
      )}

      {estado === "encontrado" && paciente && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-emerald-50 border border-emerald-200 rounded-xl p-3">
          <div>
            <span className="font-bold">Nombre: </span>
            {paciente.name}
          </div>
          <div>
            <span className="font-bold">Edad: </span>
            {calcularEdad(paciente.birth_date)}
          </div>
          <div>
            <span className="font-bold">Sexo: </span>
            {paciente.biological_sex ? ETIQUETA_SEXO[paciente.biological_sex] : "—"}
          </div>
        </div>
      )}

      {(estado === "nuevo" || estado === "registrando") && (
        <div className="space-y-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="font-medium text-amber-800">
            No hay un paciente con ese RUT. Complete los datos para registrarlo.
          </p>

          <div className="flex items-center gap-2">
            <label htmlFor="nombre" className="font-bold min-w-[70px]">
              Nombre:
            </label>
            <input
              id="nombre"
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              className={INPUT}
            />
          </div>

          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <div className="flex items-center gap-2">
              <label htmlFor="nacimiento" className="font-bold min-w-[70px]">
                Nacimiento:
              </label>
              <input
                id="nacimiento"
                type="date"
                value={fechaNacimiento}
                max={new Date().toISOString().slice(0, 10)}
                onChange={(e) => setFechaNacimiento(e.target.value)}
                className="border border-slate-300 rounded px-3 py-1 bg-white focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-4">
              <span className="font-bold">Sexo:</span>
              {(["male", "female"] as SexoBiologico[]).map((valor) => (
                <label key={valor} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="radio"
                    name="sexo"
                    checked={sexo === valor}
                    onChange={() => setSexo(valor)}
                  />
                  <span>{ETIQUETA_SEXO[valor]}</span>
                </label>
              ))}
            </div>
          </div>

          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={consentimiento}
              onChange={(e) => setConsentimiento(e.target.checked)}
              className="mt-1"
            />
            <span>
              El paciente fue informado y acepta el tratamiento de sus datos clínicos
              para su atención (consentimiento informado, versión 1.0).
            </span>
          </label>

          <button
            type="button"
            onClick={handleRegistrar}
            disabled={ocupado || !consentimiento || nombre.trim().length < 2}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold px-4 py-2 rounded-lg cursor-pointer"
          >
            {estado === "registrando" ? "Registrando..." : "Registrar paciente"}
          </button>
        </div>
      )}
    </div>
  );
};