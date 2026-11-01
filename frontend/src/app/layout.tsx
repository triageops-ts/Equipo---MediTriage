import React from "react";
import "./globals.css";

export const metadata = {
  title: "MediTriage",
  description: "Plataforma clínica de priorización ESI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="bg-slate-50 text-slate-900 min-h-screen">
        {children}
      </body>
    </html>
  );
}