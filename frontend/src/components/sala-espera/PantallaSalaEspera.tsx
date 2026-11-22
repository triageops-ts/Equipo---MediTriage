"use client";

// Pantalla pública de la sala de espera (S11-10, US-04). Solo lectura y sin login.
// Pensada para un monitor: letra grande, alto contraste y sin nada que haya que tocar.
// Solo muestra turnos anonimizados ("A-12"): nunca RUT, nombre ni ids.

import type { ReactNode } from "react";
import type { EsiLevel, SalaEsperaEntry } from "@/lib/api";
import { ESI, NIVELES_ESI } from "@/lib/esi";
import { RANGO_ESPERA, horaCorta, resumirSala, textoEstimado } from "@/lib/salaEspera";
import { useSalaEspera } from "@/lib/useSalaEspera";

/** Filas que caben en el monitor sin desplazarse. */
const MAX_LLAMADOS = 5;
const MAX_EN_ESPERA = 10;

export function PantallaSalaEspera() {
  const { filas, actualizado, error, recienLlamados } = useSalaEspera();
  const resumen = filas ? resumirSala(filas) : null;

  return (
    <div className="flex min-h-screen flex-col bg-slate-100 text-slate-900">
      <header className="flex items-center justify-between bg-slate-200 px-8 py-4 shadow-sm">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="grid size-10 grid-cols-2 gap-1">
            <span className="rounded-full bg-red-500" />
            <span className="rounded-full bg-orange-500" />
            <span className="rounded-full bg-green-500" />
            <span className="rounded-full bg-blue-500" />
          </span>
          <span className="text-3xl font-bold tracking-tight">MediTriage</span>
        </div>
        <h1 className="text-3xl font-semibold text-slate-700">Sala de espera</h1>
      </header>

      <main className="mx-auto w-full max-w-[1800px] flex-1 space-y-8 p-8">
        {error && (
          <p
            role="status"
            className="rounded-2xl border-4 border-amber-300 bg-amber-50 px-6 py-4 text-2xl font-medium text-amber-900"
          >
            Sin conexión con el servidor.
            {actualizado ? ` Mostrando datos de las ${horaCorta(actualizado)} hrs.` : " Reintentando…"}
          </p>
        )}

        {!resumen ? (
          !error && (
            <p className="py-24 text-center text-4xl text-slate-500">Cargando sala de espera…</p>
          )
        ) : (
          <>
            <Tarjeta titulo="Estado actual de urgencias">
              <div className="flex flex-wrap items-end gap-x-24 gap-y-6 px-8 pb-8">
                <Indicador valor={String(resumen.enEspera.length)} etiqueta="Pacientes en espera" />
                <Indicador
                  valor={String(resumen.promedioMin)}
                  unidad="min"
                  etiqueta="Tiempo promedio de espera"
                />
                {actualizado && (
                  <p className="ml-auto text-2xl text-slate-500">
                    Última actualización: {horaCorta(actualizado)} hrs
                  </p>
                )}
              </div>
            </Tarjeta>

            <div className="grid gap-8 xl:grid-cols-2">
              <Tarjeta titulo="Pacientes llamados">
                <ul aria-live="polite" className="divide-y-4 divide-slate-100">
                  {resumen.llamados.length === 0 ? (
                    <li className="px-8 py-10 text-center text-3xl text-slate-500">
                      Aún no hay turnos llamados.
                    </li>
                  ) : (
                    resumen.llamados.slice(0, MAX_LLAMADOS).map((f) => (
                      <FilaLlamado key={f.turno} fila={f} destacado={recienLlamados.has(f.turno)} />
                    ))
                  )}
                </ul>
              </Tarjeta>

              <Tarjeta titulo="Estado por nivel ESI">
                <ul className="divide-y-4 divide-slate-100">
                  {NIVELES_ESI.map((nivel) => (
                    <FilaNivel key={nivel} nivel={nivel} cantidad={resumen.porNivel[nivel]} />
                  ))}
                </ul>
              </Tarjeta>
            </div>

            <Tarjeta titulo="Turnos en espera · orden de atención por gravedad">
              {resumen.enEspera.length === 0 ? (
                <p className="px-8 py-10 text-center text-3xl text-slate-500">
                  No hay pacientes en espera.
                </p>
              ) : (
                <>
                  <ol className="divide-y-4 divide-slate-100">
                    {resumen.enEspera.slice(0, MAX_EN_ESPERA).map((f, i) => (
                      <FilaEspera key={f.turno} fila={f} lugar={f.posicion ?? i + 1} />
                    ))}
                  </ol>
                  {resumen.enEspera.length > MAX_EN_ESPERA && (
                    <p className="border-t-4 border-slate-100 px-8 py-4 text-2xl text-slate-500">
                      y {resumen.enEspera.length - MAX_EN_ESPERA} turnos más en espera
                    </p>
                  )}
                </>
              )}
            </Tarjeta>
          </>
        )}
      </main>

      <footer className="px-8 pb-6 text-center text-xl text-slate-500">
        Se atiende primero a quien está más grave (escala ESI), no por orden de llegada. Los
        tiempos son estimados.
      </footer>
    </div>
  );
}

function Tarjeta({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-3xl border-4 border-slate-200 bg-white">
      <h2 className="px-8 pb-4 pt-6 text-3xl font-semibold">{titulo}</h2>
      {children}
    </section>
  );
}

function Indicador({ valor, unidad, etiqueta }: { valor: string; unidad?: string; etiqueta: string }) {
  return (
    <div>
      <p className="text-7xl font-bold leading-none tabular-nums">
        {valor}
        {unidad && <span className="ml-2 text-3xl font-semibold">{unidad}</span>}
      </p>
      <p className="mt-2 text-2xl text-slate-600">{etiqueta}</p>
    </div>
  );
}

function PastillaEsi({ nivel }: { nivel: EsiLevel | null }) {
  if (nivel === null) {
    return (
      <span className="rounded-full bg-slate-400 px-5 py-2 text-2xl font-semibold text-white">
        En evaluación
      </span>
    );
  }
  return (
    <span className={`rounded-full px-5 py-2 text-2xl font-semibold ${ESI[nivel].pastilla}`}>
      ESI {nivel} · {ESI[nivel].nombre}
    </span>
  );
}

function FilaLlamado({ fila, destacado }: { fila: SalaEsperaEntry; destacado: boolean }) {
  return (
    <li
      className={[
        "flex flex-wrap items-center gap-x-6 gap-y-3 px-8 py-5 transition-colors",
        destacado ? "animate-pulse bg-blue-50" : "",
      ].join(" ")}
    >
      <span className="min-w-[5ch] text-5xl font-bold tabular-nums">{fila.turno}</span>
      <span aria-hidden="true" className="text-4xl text-slate-400">
        ⟶
      </span>
      <span className="rounded-full bg-slate-200 px-5 py-2 text-2xl font-semibold">En atención</span>
      <span className="ml-auto">
        <PastillaEsi nivel={fila.nivel_esi} />
      </span>
    </li>
  );
}

function FilaNivel({ nivel, cantidad }: { nivel: EsiLevel; cantidad: number }) {
  return (
    <li className="flex items-center gap-5 px-8 py-4">
      <span aria-hidden="true" className={`size-6 shrink-0 rounded-full ${ESI[nivel].pastilla}`} />
      <div className="min-w-0">
        <p className="text-3xl font-semibold">
          ESI {nivel} · {ESI[nivel].nombre}
        </p>
        <p className="text-xl text-slate-500">{RANGO_ESPERA[nivel]}</p>
      </div>
      <p className="ml-auto whitespace-nowrap text-2xl text-slate-600">
        <span className={`mr-2 text-5xl font-bold tabular-nums ${ESI[nivel].texto}`}>{cantidad}</span>
        en espera
      </p>
    </li>
  );
}

function FilaEspera({ fila, lugar }: { fila: SalaEsperaEntry; lugar: number }) {
  return (
    <li className="flex flex-wrap items-center gap-x-8 gap-y-3 px-8 py-5">
      <span className="w-16 text-3xl font-semibold text-slate-400 tabular-nums">{lugar}°</span>
      <span className="min-w-[5ch] text-5xl font-bold tabular-nums">{fila.turno}</span>
      <PastillaEsi nivel={fila.nivel_esi} />
      <span className="ml-auto text-right">
        <span className="block text-xl text-slate-500">Tiempo estimado</span>
        <span className="text-4xl font-semibold tabular-nums">{textoEstimado(fila)}</span>
      </span>
    </li>
  );
}
