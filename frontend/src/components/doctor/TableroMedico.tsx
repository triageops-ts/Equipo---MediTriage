"use client";

// Tablero del médico (S08-9): lista de pacientes ordenada por urgencia, con alerta
// visual y sonora para ESI 1 y 2. Pensado para leerse rápido en un turno de urgencias.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { cerrarSesion } from "@/lib/api";
import { activarSonido, silenciarSonido, sonarAlarma } from "@/lib/alarma";
import { ESI, NIVELES_ESI, esCritico, nivelVigente } from "@/lib/esi";
import { LIMITE_COLA, useColaEnVivo, type EstadoConexion } from "@/lib/useColaEnVivo";
import { ListaPacientes } from "@/components/doctor/ListaPacientes";
import { DetallePaciente } from "@/components/doctor/DetallePaciente";

const TITULO_PAGINA = "Tablero médico · MediTriage";

const CONEXION: Record<EstadoConexion, { texto: string; punto: string }> = {
  conectando: { texto: "Conectando…", punto: "bg-slate-400" },
  en_vivo: { texto: "En vivo", punto: "bg-green-500" },
  sin_conexion: {
    texto: "Sin conexión en vivo · se actualiza cada 30 s",
    punto: "bg-amber-500",
  },
};

function IconoAlerta({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="currentColor">
      <path d="M12 2 1 21h22L12 2Zm1 15h-2v-2h2v2Zm0-4h-2V9h2v4Z" />
    </svg>
  );
}

function IconoSonido({ activo }: { activo: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5" fill="currentColor">
      <path d="M3 9v6h4l5 5V4L7 9H3Z" />
      {activo ? (
        <path d="M16.5 12a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4Zm-2.5-9v2.1a7 7 0 0 1 0 13.8V21a9 9 0 0 0 0-18Z" />
      ) : (
        <path d="m19.6 12 2.4-2.4-1.4-1.4-2.4 2.4-2.4-2.4-1.4 1.4 2.4 2.4-2.4 2.4 1.4 1.4 2.4-2.4 2.4 2.4 1.4-1.4-2.4-2.4Z" />
      )}
    </svg>
  );
}

export function TableroMedico() {
  const router = useRouter();
  // sonarAlarma no hace nada mientras el sonido no se haya activado con un clic.
  const { items, resumen, nuevos, error, errorResumen, conexion, actualizado, recargar } = useColaEnVivo(sonarAlarma);
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [sonido, setSonido] = useState(false);
  const [avisoSonido, setAvisoSonido] = useState<string | null>(null);

  const lista = items ?? [];
  const seleccionado = lista.find((i) => i.episodio_id === seleccion) ?? lista[0] ?? null;
  const criticos = lista.filter(esCritico);
  const totalCriticos = resumen
    ? resumen.por_nivel[1] + resumen.por_nivel[2]
    : criticos.length;
  const sinNivel = resumen?.sin_nivel ?? lista.filter((i) => nivelVigente(i) === null).length;

  // El título de la pestaña también avisa, por si el médico está en otra ventana.
  useEffect(() => {
    document.title =
      totalCriticos > 0 ? `(${totalCriticos}) ESI 1–2 · ${TITULO_PAGINA}` : TITULO_PAGINA;
  }, [totalCriticos]);

  useEffect(() => {
    return () => {
      document.title = "MediTriage";
    };
  }, []);

  const alternarSonido = async () => {
    if (sonido) {
      await silenciarSonido();
      setSonido(false);
      return;
    }
    const listo = await activarSonido();
    setSonido(listo);
    setAvisoSonido(listo ? null : "El navegador no permitió activar el sonido.");
    if (listo) sonarAlarma(2); // prueba corta para confirmar que se escucha
  };

  const salir = async () => {
    try {
      await cerrarSesion(); // el backend borra la cookie httpOnly
    } finally {
      router.replace("/login");
    }
  };

  const estadoConexion = CONEXION[conexion];

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="flex items-center justify-between bg-slate-200 px-6 py-2">
        <span className="text-xl font-bold text-slate-900">MediTriage</span>
        <div className="flex items-center gap-4">
          <span className="text-lg text-slate-900">
            Médico de turno · <span className="font-bold">Tablero de urgencias</span>
          </span>
          <button
            type="button"
            onClick={salir}
            className="rounded-md bg-slate-900 px-3 py-1 text-lg font-semibold text-white hover:bg-slate-700"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-5 px-6 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Tablero del Médico</h1>
            <p className="text-sm text-slate-600">
              Revisa las recomendaciones de la IA y las decisiones de enfermería. Prioridad:
              pacientes ESI 1 y 2.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <p className="flex items-center gap-2 text-sm text-slate-600" aria-live="polite">
              <span className={`h-2.5 w-2.5 rounded-full ${estadoConexion.punto}`} />
              {estadoConexion.texto}
              {actualizado && (
                <span className="text-slate-400">
                  · {actualizado.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" })}
                </span>
              )}
            </p>
            <button
              type="button"
              onClick={alternarSonido}
              aria-pressed={sonido}
              className={`flex items-center gap-2 rounded-lg border-2 px-3 py-2 text-sm font-semibold ${
                sonido
                  ? "border-slate-300 bg-white text-slate-700"
                  : "animate-pulse border-red-500 bg-red-600 text-white"
              }`}
            >
              <IconoSonido activo={sonido} />
              {sonido ? "Alerta sonora activada" : "Activar alerta sonora"}
            </button>
          </div>
        </div>

        {avisoSonido && <p className="text-sm text-red-700">{avisoSonido}</p>}

        {/* Alerta destacada de ESI 1–2 */}
        <div
          role="alert"
          className={`flex items-center gap-3 rounded-xl border px-5 py-4 text-sm font-semibold ${
            totalCriticos > 0
              ? "border-red-300 bg-red-50 text-red-800"
              : "border-slate-200 bg-white text-slate-600"
          }`}
        >
          {totalCriticos > 0 ? (
            <>
              <IconoAlerta className="h-5 w-5 shrink-0 animate-pulse text-red-600" />
              {totalCriticos} paciente(s) ESI 1–2 esperando atención
            </>
          ) : items ? (
            "Sin pacientes ESI 1–2 en espera."
          ) : (
            "Cargando pacientes…"
          )}
        </div>

        {/* Contadores por nivel ESI */}
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {NIVELES_ESI.map((nivel) => (
            <li
              key={nivel}
              className={`rounded-xl border-2 border-t-4 bg-white px-4 py-3 text-center ${ESI[nivel].contador}`}
            >
              <p className={`text-3xl font-bold ${ESI[nivel].texto}`}>
                {resumen?.por_nivel[nivel] ?? lista.filter((i) => nivelVigente(i) === nivel).length}
              </p>
              <p className="text-sm text-slate-700">
                ESI {nivel} · {ESI[nivel].nombre}
              </p>
            </li>
          ))}
        </ul>
        {sinNivel > 0 && (
          <p className="text-sm text-slate-500">
            {sinNivel} paciente(s) aún sin nivel ESI (aparecen al final de la lista).
          </p>
        )}

        {error && (
          <div className="flex items-center justify-between rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <span>
              {items ? "No se pudo actualizar la lista; se muestran los últimos datos. " : ""}
              {error}
            </span>
            <button type="button" onClick={() => void recargar()} className="font-semibold underline">
              Reintentar
            </button>
          </div>
        )}

        {errorResumen && (
          <div className="flex items-center justify-between rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <span>
              No se pudieron actualizar los contadores globales. Se muestran cifras parciales de los pacientes cargados.
            </span>
            <button type="button" onClick={() => void recargar()} className="font-semibold underline">
              Reintentar
            </button>
          </div>
        )}

        {items && (
          <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-2">
            <div className="space-y-2">
              <ListaPacientes
                items={lista}
                seleccionado={seleccionado?.episodio_id ?? null}
                nuevos={nuevos}
                onSeleccionar={setSeleccion}
              />
              {lista.length >= LIMITE_COLA && (
                <p className="text-xs text-slate-500">
                  Se muestran los {LIMITE_COLA} pacientes más urgentes.
                </p>
              )}
            </div>
            <DetallePaciente item={seleccionado} />
          </div>
        )}
      </main>
    </div>
  );
}
