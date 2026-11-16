"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, iniciarSesion, obtenerSesion } from "@/lib/api";
import { vistaDelRol } from "@/lib/sesion";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Si ya hay una sesión válida, se va directo a la vista del rol.
  useEffect(() => {
    let activo = true;
    obtenerSesion()
      .then((s) => activo && router.replace(vistaDelRol(s.rol)))
      .catch(() => {});
    return () => {
      activo = false;
    };
  }, [router]);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const sesion = await iniciarSesion({ email: email.trim(), password });
      setPassword("");
      router.replace(vistaDelRol(sesion.rol));
    } catch (err) {
      setPassword("");
      if (err instanceof ApiError && err.status === 401) {
        setError("Correo o contraseña incorrectos.");
      } else if (err instanceof ApiError && err.status === 422) {
        setError("Revise el correo y la contraseña ingresados.");
      } else if (err instanceof ApiError && err.status === 0) {
        setError("No se pudo conectar con el servidor.");
      } else {
        setError("No se pudo iniciar sesión. Intente nuevamente.");
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <form
        onSubmit={enviar}
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <header>
          <h1 className="text-2xl font-bold text-slate-900">MediTriage</h1>
          <p className="text-sm text-slate-600">Inicie sesión con su cuenta del personal de salud.</p>
        </header>

        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium text-slate-700">
            Correo
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className="text-sm font-medium text-slate-700">
            Contraseña
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        {error && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={enviando}
          className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {enviando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </main>
  );
}
