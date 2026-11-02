import Link from "next/link";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { VISTAS } from "@/lib/vistas";

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <header>
          <h1 className="text-3xl font-bold text-slate-900">MediTriage</h1>
          <p className="text-slate-600">Selecciona tu vista de trabajo.</p>
        </header>
        <div className="grid gap-4 sm:grid-cols-2">
          {VISTAS.map((v) => (
            <Link
              key={v.id}
              href={v.href}
              className="rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
            >
              <Card className="h-full transition hover:shadow-md">
                <CardHeader>
                  <CardTitle>{v.titulo}</CardTitle>
                  <CardDescription>{v.descripcion}</CardDescription>
                  <p className="text-xs text-slate-500">{v.historia}</p>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
