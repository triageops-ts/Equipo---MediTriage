// Guardado de la decisión de la enfermera con reintentos (Tarjeta S07-11).
//
// Reglas de privacidad (npm run check:pii):
//  - La decisión pendiente vive SOLO en memoria: no se usa ningún almacenamiento del
//    navegador. Sobrevive a un corte de internet, no a recargar la página.
//  - Al auditar el fallo solo se envían contadores y categorías, nunca el contenido
//    clínico (nivel ESI, justificación).
import {
  ApiError,
  registrarDecision,
  reportarFalloGuardado,
  type DecisionInput,
  type DecisionResponse,
  type EventoFalloGuardado,
  type TipoErrorConexion,
} from "@/lib/api";

export const REINTENTOS_MAX = 5;
const ESPERA_BASE_MS = 2000;
const ESPERA_MAX_MS = 30000;

/** Fallos que vale la pena reintentar: sin red, o servidor caído / lento (Neon se suspende). */
export function esFalloDeConexion(e: unknown): e is ApiError {
  return (
    e instanceof ApiError &&
    (e.status === 0 || e.status === 502 || e.status === 503 || e.status === 504)
  );
}

export function tipoDeError(e: ApiError): TipoErrorConexion {
  if (e.status === 0) return "red";
  if (e.status === 504) return "timeout_servidor";
  return "servidor_no_disponible";
}

/** 2 s, 4 s, 8 s, 16 s, 30 s... (backoff exponencial con tope). */
export function esperaAntesDelIntento(intentoFallido: number): number {
  return Math.min(ESPERA_BASE_MS * 2 ** (intentoFallido - 1), ESPERA_MAX_MS);
}

export type ResultadoGuardado =
  | { estado: "guardado"; decision: DecisionResponse | null; intentos: number }
  | { estado: "fallido"; intentos: number } // se acabaron los reintentos: queda pendiente
  | { estado: "rechazado"; mensaje: string; intentos: number } // el servidor dijo que no (4xx)
  | { estado: "cancelado"; intentos: number };

export interface OpcionesGuardado {
  episodioId: string;
  datos: DecisionInput;
  /** Se llama antes de cada espera, para mostrar "reintentando en X s". */
  alReintentar?: (info: { intentos: number; proximoEnMs: number }) => void;
  señal?: AbortSignal;
  // Inyectables para las pruebas.
  registrar?: typeof registrarDecision;
  esperar?: (ms: number, señal?: AbortSignal) => Promise<void>;
}

function dormir(ms: number, señal?: AbortSignal): Promise<void> {
  return new Promise((resolver) => {
    const t = setTimeout(resolver, ms);
    señal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        resolver();
      },
      { once: true },
    );
  });
}

// --- Avisos de auditoría pendientes de enviar (también solo en memoria) ---
const avisosPendientes: EventoFalloGuardado[] = [];

/** Envía los avisos acumulados. Si sigue sin haber conexión, los conserva para después. */
export async function enviarAvisosPendientes(
  enviar: typeof reportarFalloGuardado = reportarFalloGuardado,
): Promise<void> {
  while (avisosPendientes.length > 0) {
    const aviso = avisosPendientes[0];
    try {
      await enviar(aviso);
    } catch (e) {
      if (esFalloDeConexion(e)) return; // sigue sin conexión: se reintenta luego
      // 4xx (por ejemplo episodio inexistente): reenviarlo no serviría, se descarta.
    }
    avisosPendientes.shift();
  }
}

export function avisosSinEnviar(): number {
  return avisosPendientes.length;
}

/** Solo para pruebas. */
export function _vaciarAvisosParaPruebas(): void {
  avisosPendientes.length = 0;
}

/**
 * Intenta guardar la decisión; si falla por conexión, reintenta con espera creciente.
 * Siempre que hubo al menos un fallo de conexión deja un aviso para la auditoría.
 */
export async function guardarConReintentos(
  op: OpcionesGuardado,
): Promise<ResultadoGuardado> {
  const registrar = op.registrar ?? registrarDecision;
  const esperar = op.esperar ?? dormir;

  let intentos = 0;
  let ultimoError: ApiError | null = null;
  const primerFallo = { hora: "" };

  while (intentos < REINTENTOS_MAX) {
    if (op.señal?.aborted) return { estado: "cancelado", intentos };
    intentos += 1;

    try {
      const decision = await registrar(op.episodioId, op.datos);
      if (ultimoError) encolarAviso(op, ultimoError, intentos, true, primerFallo.hora);
      return { estado: "guardado", decision, intentos };
    } catch (e) {
      if (!esFalloDeConexion(e)) {
        // 409 "ya tiene una decisión" después de un fallo de conexión: el intento anterior
        // sí llegó al servidor y solo se perdió la respuesta, así que ya está guardada.
        // Otros 409 (por ejemplo, "aún no hay sugerencia de la IA") NO son guardado.
        if (
          e instanceof ApiError &&
          e.status === 409 &&
          ultimoError &&
          e.message.includes("ya tiene una decisión")
        ) {
          encolarAviso(op, ultimoError, intentos, true, primerFallo.hora);
          return { estado: "guardado", decision: null, intentos };
        }
        const mensaje = e instanceof ApiError ? e.message : "Error inesperado al guardar.";
        return { estado: "rechazado", mensaje, intentos };
      }

      if (!ultimoError) primerFallo.hora = new Date().toISOString();
      ultimoError = e;

      if (intentos >= REINTENTOS_MAX) break;
      const proximoEnMs = esperaAntesDelIntento(intentos);
      op.alReintentar?.({ intentos, proximoEnMs });
      await esperar(proximoEnMs, op.señal);
    }
  }

  if (ultimoError) encolarAviso(op, ultimoError, intentos, false, primerFallo.hora);
  return { estado: "fallido", intentos };
}

function encolarAviso(
  op: OpcionesGuardado,
  error: ApiError,
  intentos: number,
  recuperado: boolean,
  primerFalloCliente: string,
): void {
  avisosPendientes.push({
    episodio_id: op.episodioId,
    usuario_id: op.datos.usuario_id,
    tipo_error: tipoDeError(error),
    intentos,
    recuperado,
    primer_fallo_cliente: primerFalloCliente,
  });
  void enviarAvisosPendientes();
}