"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  cerrarSesion,
  obtenerAuditLogs,
  verificarCadenaAuditoria,
  type AuditLogEntry,
  type VerificacionCadena,
} from "@/lib/api";

const POR_PAGINA = 20;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function fechaUtc(iso: string): string {
  // El backend guarda la hora en UTC sin zona: se muestra tal cual, marcada como UTC.
  return `${iso.replace("T", " ").slice(0, 19)} UTC`;
}

function corto(id: string | null | undefined): string {
  return id ? `${id.slice(0, 8)}…` : "—";
}

// Vista de solo lectura: no hay botones para editar ni borrar (la tabla es inmutable).
export function TablaAuditoria() {
  const router = useRouter();
  const [pagina, setPagina] = useState(0);

  // Lo que escribe el auditor y lo que ya se aplicó (se consulta al pulsar "Filtrar").
  const [episodioTxt, setEpisodioTxt] = useState("");
  const [usuarioTxt, setUsuarioTxt] = useState("");
  const [soloModificados, setSoloModificados] = useState(false);
  const [filtros, setFiltros] = useState({
    episodio_id: "",
    usuario_id: "",
    solo_modificados: false,
  });
  const [errorFiltro, setErrorFiltro] = useState<string | null>(null);

  const [verificacion, setVerificacion] = useState<VerificacionCadena | null>(null);
  const [verificando, setVerificando] = useState(false);
  const [errorVerificacion, setErrorVerificacion] = useState<string | null>(null);

  // Resultado de la última consulta, con la clave (filtros + página) a la que corresponde.
  // "Cargando" es no tener aún el resultado de la consulta actual.
  const clave = JSON.stringify([filtros, pagina]);
  const [resultado, setResultado] = useState<{
    clave: string;
    registros: AuditLogEntry[];
    error: string | null;
  } | null>(null);
  const cargando = resultado?.clave !== clave;
  const registros = resultado?.clave === clave ? resultado.registros : [];
  const error = resultado?.clave === clave ? resultado.error : null;

  useEffect(() => {
    let vigente = true;
    obtenerAuditLogs({
      episodio_id: filtros.episodio_id || undefined,
      usuario_id: filtros.usuario_id || undefined,
      hay_discrepancia: filtros.solo_modificados ? true : undefined,
      skip: pagina * POR_PAGINA,
      limit: POR_PAGINA,
    })
      .then((datos) => {
        if (vigente) setResultado({ clave, registros: datos, error: null });
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        const mensaje = e instanceof ApiError ? e.message : "No se pudo cargar la auditoría.";
        setResultado({ clave, registros: [], error: mensaje });
      });
    return () => {
      vigente = false;
    };
  }, [clave, filtros, pagina]);

  const filtrar = (e: React.FormEvent) => {
    e.preventDefault();
    const ep = episodioTxt.trim();
    const us = usuarioTxt.trim();
    if ((ep && !UUID.test(ep)) || (us && !UUID.test(us))) {
      setErrorFiltro("El episodio y el usuario deben ser identificadores UUID válidos.");
      return;
    }
    setErrorFiltro(null);
    setPagina(0);
    setFiltros({ episodio_id: ep, usuario_id: us, solo_modificados: soloModificados });
  };

  const limpiar = () => {
    setEpisodioTxt("");
    setUsuarioTxt("");
    setSoloModificados(false);
    setErrorFiltro(null);
    setPagina(0);
    setFiltros({ episodio_id: "", usuario_id: "", solo_modificados: false });
  };

  const verificar = async () => {
    setVerificando(true);
    setErrorVerificacion(null);
    try {
      setVerificacion(await verificarCadenaAuditoria());
    } catch (e) {
      setVerificacion(null);
      setErrorVerificacion(
        e instanceof ApiError ? e.message : "No se pudo verificar la cadena.",
      );
    } finally {
      setVerificando(false);
    }
  };

  const salir = async () => {
    try {
      await cerrarSesion();
    } finally {
      router.replace("/login");
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-sm text-slate-600 hover:underline">
            ← Volver al inicio
          </Link>
          <button type="button" onClick={salir} className="text-sm text-slate-600 hover:underline">
            Cerrar sesión
          </button>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-slate-900">Auditoría clínico-algorítmica</h1>
          <p className="text-slate-600">
            Registro inmutable de lo que sugirió la IA y de lo que decidió el personal. Solo
            lectura.
          </p>
        </div>

        <section className="rounded-lg border border-slate-200 bg-white p-4" aria-label="Integridad">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={verificar}
              disabled={verificando}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:opacity-60"
            >
              {verificando ? "Verificando…" : "Verificar integridad de la cadena"}
            </button>
            {verificacion?.valida && (
              <p role="status" className="text-sm font-medium text-emerald-700">
                Cadena íntegra: {verificacion.registros_verificados} registros verificados.
              </p>
            )}
            {verificacion && !verificacion.valida && verificacion.primer_registro_alterado && (
              <p role="alert" className="text-sm font-medium text-red-700">
                Cadena alterada. Primer registro afectado:{" "}
                <code className="font-mono">
                  {verificacion.primer_registro_alterado.registro_id}
                </code>{" "}
                ({verificacion.primer_registro_alterado.motivo}).
              </p>
            )}
            {errorVerificacion && (
              <p role="alert" className="text-sm text-red-700">
                {errorVerificacion}
              </p>
            )}
          </div>
        </section>

        <form
          onSubmit={filtrar}
          className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
        >
          <label className="text-sm text-slate-700">
            Episodio
            <input
              value={episodioTxt}
              onChange={(e) => setEpisodioTxt(e.target.value)}
              placeholder="UUID del episodio"
              className="mt-1 block w-72 rounded-md border border-slate-300 px-2 py-1.5 font-mono text-xs"
            />
          </label>
          <label className="text-sm text-slate-700">
            Usuario
            <input
              value={usuarioTxt}
              onChange={(e) => setUsuarioTxt(e.target.value)}
              placeholder="UUID del usuario"
              className="mt-1 block w-72 rounded-md border border-slate-300 px-2 py-1.5 font-mono text-xs"
            />
          </label>
          <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={soloModificados}
              onChange={(e) => setSoloModificados(e.target.checked)}
            />
            Solo modificados manualmente
          </label>
          <button
            type="submit"
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
          >
            Filtrar
          </button>
          <button
            type="button"
            onClick={limpiar}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
          >
            Limpiar
          </button>
          {errorFiltro && (
            <p role="alert" className="w-full text-sm text-red-700">
              {errorFiltro}
            </p>
          )}
        </form>

        {error && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </p>
        )}

        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase text-slate-600">
              <tr>
                <th className="px-3 py-2">Fecha</th>
                <th className="px-3 py-2">Evento</th>
                <th className="px-3 py-2">Episodio</th>
                <th className="px-3 py-2">Actor</th>
                <th className="px-3 py-2">Sugerencia IA</th>
                <th className="px-3 py-2">Decisión final</th>
                <th className="px-3 py-2">Modificado manualmente</th>
                <th className="px-3 py-2">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {cargando && (
                <tr>
                  <td colSpan={8} className="px-3 py-6 text-center text-slate-500">
                    Cargando…
                  </td>
                </tr>
              )}
              {!cargando && !error && registros.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-3 py-6 text-center text-slate-500">
                    No hay registros para estos filtros.
                  </td>
                </tr>
              )}
              {!cargando &&
                registros.map((r) => (
                  <tr key={r.registro_id} className="border-t border-slate-200 align-top">
                    <td className="whitespace-nowrap px-3 py-2">{fechaUtc(r.fecha_hora_evento)}</td>
                    <td className="px-3 py-2 font-mono text-xs">{r.evento_tipo}</td>
                    <td className="px-3 py-2 font-mono text-xs" title={r.episodio_id}>
                      {corto(r.episodio_id)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs" title={r.usuario_id_actor ?? ""}>
                      {corto(r.usuario_id_actor)}
                    </td>
                    <td className="px-3 py-2">{r.sugerencia_ia ?? "—"}</td>
                    <td className="px-3 py-2">{r.decision_final ?? "—"}</td>
                    <td className="px-3 py-2">
                      {r.hay_discrepancia ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                          Modificado manualmente
                        </span>
                      ) : (
                        <span className="text-slate-400">No</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <details>
                        <summary className="cursor-pointer text-xs text-slate-600">Ver</summary>
                        <div className="mt-2 max-w-md space-y-2 text-xs text-slate-700">
                          {r.prompt_enviado && (
                            <pre className="whitespace-pre-wrap break-words rounded bg-slate-50 p-2">
                              {r.prompt_enviado}
                            </pre>
                          )}
                          <p className="break-all font-mono">hash anterior: {r.hash_anterior}</p>
                          <p className="break-all font-mono">hash actual: {r.hash_actual}</p>
                        </div>
                      </details>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-sm text-slate-700">
          <button
            type="button"
            onClick={() => setPagina((p) => Math.max(0, p - 1))}
            disabled={pagina === 0 || cargando}
            className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-100 disabled:opacity-50"
          >
            ← Anterior
          </button>
          <span>Página {pagina + 1}</span>
          <button
            type="button"
            onClick={() => setPagina((p) => p + 1)}
            disabled={registros.length < POR_PAGINA || cargando}
            className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-100 disabled:opacity-50"
          >
            Siguiente →
          </button>
        </div>
      </div>
    </main>
  );
}
