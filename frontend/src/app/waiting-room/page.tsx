import type { Metadata } from "next";
import { PantallaSalaEspera } from "@/components/sala-espera/PantallaSalaEspera";

// Pantalla pública (US-04): no lleva GuardaRol ni login. Solo turnos anonimizados.
export const metadata: Metadata = {
  title: "Sala de espera · MediTriage",
};

export default function WaitingRoomPage() {
  return <PantallaSalaEspera />;
}
