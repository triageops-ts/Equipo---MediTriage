import type { ColaTriageItem } from "@/lib/api";
import {
  ESI,
  ETIQUETA_REVISION,
  codigoEpisodio,
  edadTexto,
  esCritico,
  esperaTexto,
  estadoRevision,
  nivelVigente,
  sexoCorto,
} from "@/lib/esi";

interface Props {
  items: ColaTriageItem[];
  seleccionado: string | null;
  /** Episodios ESI 1–2 que acaban de llegar: se resaltan unos segundos. */
  nuevos: ReadonlySet<string>;
  onSeleccionar: (episodioId: string) => void;
}

export function ListaPacientes({ items, seleccionado, nuevos, onSeleccionar }: Props) {
  return (
    <section
      aria-labelledby="titulo-lista"
      className="overflow-hidden rounded-2xl border-4 border-slate-200 bg-white"
    >
      <h2 id="titulo-lista" className="border-b border-slate-200 px-4 py-3 font-semibold text-slate-900">
        Pacientes en sala
      </h2>

      {items.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-slate-500">
          No hay pacientes en espera.
        </p>
      ) : (
        <ul className="divide-y divide-slate-200">
          {items.map((item) => {
            const nivel = nivelVigente(item);
            const revision = ETIQUETA_REVISION[estadoRevision(item)];
            const activo = item.episodio_id === seleccionado;
            const critico = esCritico(item);
            const nuevo = nuevos.has(item.episodio_id);

            return (
              <li key={item.episodio_id}>
                <button
                  type="button"
                  onClick={() => onSeleccionar(item.episodio_id)}
                  aria-current={activo ? "true" : undefined}
                  className={[
                    "flex w-full items-center gap-4 border-l-4 px-4 py-3 text-left transition-colors hover:bg-slate-50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-slate-900",
                    critico
                      ? nivel === 1
                        ? "border-l-red-500"
                        : "border-l-orange-500"
                      : "border-l-transparent",
                    activo ? "bg-slate-100" : "",
                    nuevo ? "bg-red-50" : "",
                  ].join(" ")}
                >
                  <span
                    className={`w-16 shrink-0 rounded-full px-2 py-1 text-center text-sm font-semibold ${
                      nivel ? ESI[nivel].pastilla : "bg-slate-200 text-slate-600"
                    }`}
                  >
                    {nivel ? `ESI ${nivel}` : "S/N"}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold text-slate-900">
                      {codigoEpisodio(item.episodio_id)}
                      {nuevo && (
                        <span className="ml-2 animate-pulse rounded bg-red-600 px-1.5 py-0.5 text-xs font-bold text-white">
                          NUEVO
                        </span>
                      )}
                    </span>
                    <span className="block text-sm text-slate-600">
                      {edadTexto(item.patient.age)} · {sexoCorto(item.patient.biological_sex)} ·{" "}
                      {esperaTexto(item.minutos_espera)}
                    </span>
                  </span>

                  <span className={`shrink-0 text-sm font-medium ${revision.clase}`}>
                    {revision.texto}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
