"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { cerrarSesion } from "@/lib/api";

interface Props {
  titulo: string;
  descripcion: string;
  historia: string;
}

export function PlaceholderView({ titulo, descripcion, historia }: Props) {
  const router = useRouter();

  const salir = async () => {
    try {
      await cerrarSesion(); // el backend borra la cookie httpOnly
    } finally {
      router.replace("/login");
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-sm text-slate-600 hover:underline">
            ← Volver al inicio
          </Link>
          <button
            type="button"
            onClick={salir}
            className="text-sm text-slate-600 hover:underline"
          >
            Cerrar sesión
          </button>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">{titulo}</h1>
        <p className="text-slate-600">{descripcion}</p>
        <p className="rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
          Vista en construcción ({historia}).
        </p>
      </div>
    </main>
  );
}