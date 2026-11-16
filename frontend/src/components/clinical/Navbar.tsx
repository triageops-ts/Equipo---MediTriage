"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cerrarSesion } from "@/lib/api";

export const Navbar = () => {
  const router = useRouter();

  const salir = async () => {
    try {
      await cerrarSesion(); // el backend borra la cookie httpOnly
    } finally {
      router.replace("/login");
    }
  };

  return (
    <header className="bg-[#0e1726] text-white px-6 py-3 flex justify-between items-center text-sm font-semibold shadow-md">
      <Link href="/" className="hover:underline">MediTriage</Link>
      <div className="flex items-center gap-4">
        <span>Enf. usuario - Box Triage 1</span>
        <button type="button" onClick={salir} className="hover:underline">
          Cerrar sesión
        </button>
      </div>
    </header>
  );
};
