import type { ReactNode } from "react";
import { GuardaRol } from "@/components/auth/GuardaRol";

export default function DoctorLayout({ children }: { children: ReactNode }) {
  return <GuardaRol rol="medico">{children}</GuardaRol>;
}
