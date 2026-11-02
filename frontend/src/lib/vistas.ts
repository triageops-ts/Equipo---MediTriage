export const VISTAS = [
  {
    id: "nurse",
    href: "/nurse",
    titulo: "Enfermería",
    descripcion: "Formulario de triage: signos vitales y sugerencia ESI.",
    historia: "US-01 / US-02",
  },
  {
    id: "doctor",
    href: "/doctor",
    titulo: "Médico de turno",
    descripcion: "Tablero en tiempo real con alertas de riesgo vital (ESI 1 y 2).",
    historia: "US-03",
  },
  {
    id: "auditor",
    href: "/auditor",
    titulo: "Auditoría",
    descripcion: "Registro inmutable de las decisiones de la IA y del profesional.",
    historia: "US-05",
  },
  {
    id: "waiting-room",
    href: "/waiting-room",
    titulo: "Sala de espera",
    descripcion: "Pantalla pública con turnos anonimizados.",
    historia: "US-04",
  },
] as const;