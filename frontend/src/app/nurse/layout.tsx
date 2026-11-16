import type { ReactNode } from "react";
import { GuardaRol } from "@/components/auth/GuardaRol";

export default function NurseLayout({ children }: { children: ReactNode }) {
  return <GuardaRol rol="enfermero">{children}</GuardaRol>;
}
