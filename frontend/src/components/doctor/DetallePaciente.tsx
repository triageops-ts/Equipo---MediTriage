import type { ColaTriageItem, EsiLevel } from "@/lib/api";
import {
  ESI,
  codigoEpisodio,
  edadTexto,
  esperaTexto,
  sexoLargo,
} from "@/lib/esi";

const ESTADO_EPISODIO: Record<ColaTriageItem["estado"], string> = {
  en_espera: "En espera",
  en_atencion: "En atención",
  cerrado: "Cerrado",
};

function hora(fechaIso: string): string {
  // El backend guarda UTC sin zona: se agrega la Z para que el navegador lo convierta a hora local.
  const fecha = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(fechaIso) ? fechaIso : `${fechaIso}Z`);
  return Number.isNaN(fecha.getTime())
    ? "—"
    : fecha.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
}

function RecuadroNivel({
  titulo,
  nivel,
  destacado,
  vacio,
}: {
  titulo: string;
  nivel: EsiLevel | null | undefined;
  destacado: boolean;
  vacio: string;
}) {
  const estilo = nivel ? ESI[nivel] : null;
  return (
    <div
      className={`rounded-xl border-2 px-4 py-3 ${
        destacado && estilo ? estilo.recuadro : "border-slate-200 bg-white"
      }`}
    >
      <p className="text-sm text-slate-600">{titulo}</p>
      {estilo && nivel ? (
        <p className={`text-xl font-bold ${estilo.texto}`}>
          ESI {nivel} · {estilo.nombre}
        </p>
      ) : (
        <p className="text-base font-medium text-slate-500">{vacio}</p>
      )}
    </div>
  );
}

export function DetallePaciente({ item }: { item: ColaTriageItem | null }) {
  if (!item) {
    return (
      <section className="rounded-2xl bg-white p-6 text-sm text-slate-500">
        Seleccione un paciente para ver su detalle.
      </section>
    );
  }

  const sugerido = item.nivel_esi_sugerido ?? null;
  const final = item.nivel_esi_final ?? null;
  const difiere = sugerido !== null && final !== null && sugerido !== final;

  return (
    <section aria-labelledby="titulo-detalle" className="space-y-5 rounded-2xl bg-white p-6">
      <div>
        <h2 id="titulo-detalle" className="text-2xl font-bold text-slate-900">
          {codigoEpisodio(item.episodio_id)}
        </h2>
        <p className="text-sm text-slate-600">
          {edadTexto(item.patient.age)} · {sexoLargo(item.patient.biological_sex)} ·{" "}
          {ESTADO_EPISODIO[item.estado]}
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
          <dt className="text-xs text-slate-500">Tiempo de espera</dt>
          <dd className="text-lg font-semibold text-slate-900">
            {esperaTexto(item.minutos_espera).replace("espera ", "")}
          </dd>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
          <dt className="text-xs text-slate-500">Hora de ingreso</dt>
          <dd className="text-lg font-semibold text-slate-900">{hora(item.fecha_hora_ingreso)}</dd>
        </div>
      </dl>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <RecuadroNivel
          titulo="Recomendación IA"
          nivel={sugerido}
          destacado
          vacio="Aún sin evaluar"
        />
        <RecuadroNivel
          titulo="Decisión enfermería"
          nivel={final}
          destacado={false}
          vacio="Pendiente"
        />
      </div>

      {difiere && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Enfermería modificó el nivel sugerido por la IA (ESI {sugerido} → ESI {final}).
        </p>
      )}

      <p className="text-xs text-slate-500">
        Por privacidad, el tablero identifica a cada paciente con el código del episodio, sin nombre
        ni RUT. Toda confirmación o cambio queda registrado en el registro de auditoría
        (inmutable, 5 años).
      </p>
    </section>
  );
}
