import React from "react";
import Link from "next/link";

export const Navbar = () => (
  <header className="bg-[#0e1726] text-white px-6 py-3 flex justify-between items-center text-sm font-semibold shadow-md">
    <Link href="/" className="hover:underline">MediTriage</Link>
    <span>Enf. usuario - Box Triage 1</span>
  </header>
);