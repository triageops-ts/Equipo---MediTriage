// Alerta sonora del tablero médico (S08-9).
//
// Se genera con Web Audio (sin archivos de sonido). Los navegadores no dejan reproducir
// audio hasta que el usuario interactúa con la página, por eso el sonido se activa con
// un botón: activarSonido() debe llamarse desde un clic.

let contexto: AudioContext | null = null;

export function sonidoDisponible(): boolean {
  return typeof window !== "undefined" && typeof window.AudioContext === "function";
}

/** Prepara el audio. Devuelve true si el navegador lo dejó listo. */
export async function activarSonido(): Promise<boolean> {
  if (!sonidoDisponible()) return false;
  contexto ??= new AudioContext();
  try {
    await contexto.resume();
  } catch {
    return false;
  }
  return contexto.state === "running";
}

/**
 * Suena la alarma. ESI 1: tres pitidos agudos. ESI 2: dos pitidos algo más graves.
 * Si el sonido no se activó, no hace nada.
 */
export function sonarAlarma(nivel: 1 | 2): void {
  if (!contexto || contexto.state !== "running") return;
  const pitidos = nivel === 1 ? 3 : 2;
  const frecuencia = nivel === 1 ? 988 : 784;
  const inicio = contexto.currentTime + 0.05;

  for (let i = 0; i < pitidos; i++) {
    const t = inicio + i * 0.28;
    const oscilador = contexto.createOscillator();
    const volumen = contexto.createGain();
    oscilador.type = "square";
    oscilador.frequency.value = frecuencia;
    volumen.gain.setValueAtTime(0.0001, t);
    volumen.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
    volumen.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
    oscilador.connect(volumen).connect(contexto.destination);
    oscilador.start(t);
    oscilador.stop(t + 0.2);
  }
}

/** Silencia la alarma hasta que se vuelva a activar. */
export async function silenciarSonido(): Promise<void> {
  try {
    await contexto?.suspend();
  } catch {
    // si el navegador no deja suspender, sonarAlarma igual revisa el estado
  }
}
