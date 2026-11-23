#!/usr/bin/env node
/*
 * Falla (código 1) si en src/ aparece:
 *   1. almacenamiento del navegador: localStorage, sessionStorage, IndexedDB, cookies,
 *      Cache API, navigator.storage;
 *   2. console.* (puede imprimir datos del paciente); si es seguro, marcar la línea con "// pii-ok";
 *   3. un <input>/<textarea> de datos personales sin autoComplete (ver lib/privacidad.ts).
 *   4. en la vista pública de la sala de espera (US-04, S11-11): campos o palabras de datos
 *      personales o clínicos, formularios, sesión/token, o pedir algo más que GET /sala-espera.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("../src", import.meta.url));

const PROHIBIDO = [
  [/\b(localStorage|sessionStorage|indexedDB|openDatabase)\b/, "almacenamiento del navegador"],
  [/\bdocument\.cookie\b/, "cookies desde JavaScript"],
  [/\bnavigator\.storage\b/, "navigator.storage"],
  [/\bcaches\.(open|put|match)\b/, "Cache API"],
  [/\bconsole\.\w+\(/, "console.* (agrega // pii-ok si es seguro)"],
];

// Campos que reciben datos personales (por id o name).
const CAMPO_PII =
  /\b(?:id|name)=["'](rut|run|nombre|name|alergias?|nacimiento|birth_date|anamnesis|email|correo|telefono|phone|direccion|address)["']/;

function archivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n);
    if (statSync(ruta).isDirectory()) return archivos(ruta);
    return /\.(ts|tsx)$/.test(n) ? [ruta] : [];
  });
}


function etiquetasDeCampo(texto) {
  const etiquetas = [];
  const inicio = /<(input|textarea)\b/g;
  let m;
  while ((m = inicio.exec(texto))) {
    let i = m.index + m[0].length;
    let llaves = 0;
    let comilla = null;
    for (; i < texto.length; i++) {
      const c = texto[i];
      if (comilla) {
        if (c === comilla) comilla = null;
      } else if (c === '"' || c === "'" || c === "`") comilla = c;
      else if (c === "{") llaves++;
      else if (c === "}") llaves--;
      else if (c === ">" && llaves === 0) break;
    }
    etiquetas.push({ texto: texto.slice(m.index, i + 1), linea: texto.slice(0, m.index).split("\n").length });
    inicio.lastIndex = i;
  }
  return etiquetas;
}

const problemas = [];
for (const archivo of archivos(RAIZ)) {
  const texto = readFileSync(archivo, "utf8");
  const nombre = relative(join(RAIZ, ".."), archivo);

  texto.split("\n").forEach((linea, n) => {
    if (linea.includes("pii-ok")) return;
    for (const [patron, motivo] of PROHIBIDO) {
      if (patron.test(linea)) problemas.push(`${nombre}:${n + 1}  ${motivo}`);
    }
  });

  for (const { texto: tag, linea } of etiquetasDeCampo(texto)) {
    if (CAMPO_PII.test(tag) && !/autoComplete=|CAMPO_PRIVADO/.test(tag)) {
      problemas.push(`${nombre}:${linea}  campo con datos personales sin autoComplete="off"`);
    }
  }
}

// ---- VISTA PÚBLICA (US-04, S11-11) -------------------------------------------------
// La pantalla de la sala de espera no tiene login y se ve en un televisor. Aquí se revisa que
// su código no pueda llegar a mostrar datos personales ni clínicos, aunque alguien lo cambie.
const VISTA_PUBLICA = [
  "app/waiting-room",
  "components/sala-espera",
  "lib/salaEspera.ts",
  "lib/useSalaEspera.ts",
];

// Campos que la API pública sí puede entregar (los mismos de backend/app/schemas/sala_espera.py).
const CAMPOS_SALA = ["turno", "nivel_esi", "estado", "posicion", "minutos_espera", "tiempo_estimado_min"];

// Datos personales o clínicos: no pueden aparecer como código en la vista pública.
const DATO_PERSONAL =
  /\b(rut|run|patient_id|paciente_id|episodio_id|episodioId|full_name|nombre_completo|nombre_paciente|patient_name|email|correo|telefono|phone|direccion|address|birth_date|nacimiento|anamnesis|alergias?|sintomas?|signos_vitales|justificacion|sugerencia_ia|decision_final|diagnostico)\b/i;

// Sesión, token o canales que exigen login: la pantalla pública no los usa.
const SESION = /\b(sesion|useSesion|GuardaRol|Authorization|Bearer|token|jwt|WebSocket|useColaEnVivo)\b/i;

// Lo único que la vista pública puede importar de lib/api.
const IMPORTS_API_PERMITIDOS = new Set(["ApiError", "obtenerSalaEspera", "SalaEsperaEntry", "EsiLevel", "EstadoEpisodio"]);

function sinComentarios(texto) {
  // Quita /* ... */ y // ... conservando los saltos de línea (para no mover los números de línea).
  return texto
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/(^|[^:"'`])\/\/[^\n]*/g, "$1");
}

function archivosVistaPublica() {
  return VISTA_PUBLICA.flatMap((entrada) => {
    const ruta = join(RAIZ, entrada);
    try {
      return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta];
    } catch {
      problemas.push(`src/${entrada}  vista pública: no existe (si la moviste, actualiza VISTA_PUBLICA en check-pii.mjs)`);
      return [];
    }
  });
}

for (const archivo of archivosVistaPublica()) {
  const nombre = relative(join(RAIZ, ".."), archivo);
  const codigo = sinComentarios(readFileSync(archivo, "utf8"));

  codigo.split("\n").forEach((linea, n) => {
    const dato = DATO_PERSONAL.exec(linea);
    if (dato) problemas.push(`${nombre}:${n + 1}  vista pública con dato personal o clínico ("${dato[0]}")`);
    const sesion = SESION.exec(linea);
    if (sesion) problemas.push(`${nombre}:${n + 1}  vista pública con sesión o canal que exige login ("${sesion[0]}")`);
    if (/credentials\s*:\s*["'](include|same-origin)["']/.test(linea)) {
      problemas.push(`${nombre}:${n + 1}  vista pública enviando cookies (credentials debe ser "omit")`);
    }
  });

  if (/<(input|textarea|select|form)\b/.test(codigo)) {
    problemas.push(`${nombre}  vista pública con formulario o campo de texto (no debe pedir datos)`);
  }

  for (const m of codigo.matchAll(/import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+["']@\/lib\/api["']/g)) {
    for (const nombreImportado of m[1].split(",").map((s) => s.trim().replace(/^type\s+/, "")).filter(Boolean)) {
      if (!IMPORTS_API_PERMITIDOS.has(nombreImportado)) {
        problemas.push(`${nombre}  vista pública importa "${nombreImportado}" de lib/api (solo puede usar GET /sala-espera)`);
      }
    }
  }
}

// El tipo SalaEsperaEntry y la función que consulta la sala, en lib/api.ts.
{
  const api = sinComentarios(readFileSync(join(RAIZ, "lib/api.ts"), "utf8"));
  const tipo = /export interface SalaEsperaEntry\s*\{([\s\S]*?)\n\}/.exec(api);
  if (!tipo) {
    problemas.push("src/lib/api.ts  no encontré la interfaz SalaEsperaEntry (vista pública)");
  } else {
    const campos = [...tipo[1].matchAll(/^\s*([A-Za-z_]\w*)\??\s*:/gm)].map((m) => m[1]);
    for (const c of campos) {
      if (!CAMPOS_SALA.includes(c)) problemas.push(`src/lib/api.ts  SalaEsperaEntry tiene un campo no permitido en la sala pública: "${c}"`);
    }
  }
  const funcion = /export function obtenerSalaEspera[\s\S]*?\n\}/.exec(api);
  if (!funcion || !/credentials\s*:\s*["']omit["']/.test(funcion[0])) {
    problemas.push('src/lib/api.ts  obtenerSalaEspera debe llamar con credentials: "omit" (sin cookies ni sesión)');
  }
}


if (problemas.length > 0) {
  console.error("check:pii — encontré problemas:\n" + problemas.map((p) => "  - " + p).join("\n"));
  process.exit(1);
}
console.log("check:pii — sin hallazgos (almacenamiento, console.*, autocompletado de campos con PII y vista pública de la sala).");
