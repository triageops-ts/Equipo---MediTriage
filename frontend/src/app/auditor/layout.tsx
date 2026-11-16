import type { ReactNode } from "react";
import { GuardaRol } from "@/components/auth/GuardaRol";

export default function AuditorLayout({ children }: { children: ReactNode }) {
  return <GuardaRol rol="auditor">{children}</GuardaRol>;
}
