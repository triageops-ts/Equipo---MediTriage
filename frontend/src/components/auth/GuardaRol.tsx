"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { obtenerSesion, type RolUsuario } from "@/lib/api";
import { vistaDelRol } from "@/lib/sesion";

interface Props {
  /** Rol que puede abrir esta vista. */
  rol: RolUsuario;
  children: ReactNode;
}

/**
 * Guarda de ruta por rol. El navegador no puede leer la cookie httpOnly, así que le pregunta
 * al backend quién es (GET /auth/me). Sin sesión -> /login; con otro rol -> a su propia vista.
 * No muestra la vista hasta confirmar el rol. La seguridad real está en el backend (401/403).
 */
export function GuardaRol({ rol, children }: Props) {
  const router = useRouter();
  const [permitido, setPermitido] = useState(false);

  useEffect(() => {
    let activo = true;
    obtenerSesion()
      .then((sesion) => {
        if (!activo) return;
        if (sesion.rol === rol) setPermitido(true);
        else router.replace(vistaDelRol(sesion.rol));
      })
      .catch(() => {
        // Sin sesión (401), sesión vencida o backend caído: se vuelve al login.
        if (activo) router.replace("/login");
      });
    return () => {
      activo = false;
    };
  }, [rol, router]);

  if (!permitido) {
    return (
      <main className="min-h-screen bg-slate-50 p-6 text-sm text-slate-500" aria-busy="true">
        Verificando sesión…
      </main>
    );
  }
  return <>{children}</>;
}
