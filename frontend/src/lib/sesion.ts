import type { RolUsuario } from "@/lib/api";

// Vista de trabajo de cada rol. El rol "admin" existe en el contrato pero aún no tiene vista.
export const VISTA_POR_ROL: Partial<Record<RolUsuario, string>> = {
  enfermero: "/nurse",
  medico: "/doctor",
  auditor: "/auditor",
};

/** A dónde mandar a un usuario según su rol (o al login si no tiene vista). */
export function vistaDelRol(rol: RolUsuario): string {
  return VISTA_POR_ROL[rol] ?? "/login";
}
