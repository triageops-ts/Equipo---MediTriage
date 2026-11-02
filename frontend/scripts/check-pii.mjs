#!/usr/bin/env node
/**
 * Revisión rápida de PII en el navegador (tarjeta S06-5). Sin dependencias.
 *   npm run check:pii
 *
 * Falla (código 1) si en src/ aparece:
 *   1. almacenamiento del navegador: localStorage, sessionStorage, IndexedDB, cookies,
 *      Cache API, navigator.storage;
 *   2. console.* (puede imprimir datos del paciente); si es seguro, marcar la línea con "// pii-ok";
 *   3. un <input>/<textarea> de datos personales sin autoComplete (ver lib/privacidad.ts).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const RAIZ = new URL("../src", import.meta.url).pathname;

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

/** Devuelve cada etiqueta <input ...> / <textarea ...> completa (respeta llaves y comillas). */
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

if (problemas.length > 0) {
  console.error("check:pii — encontré problemas:\n" + problemas.map((p) => "  - " + p).join("\n"));
  process.exit(1);
}
console.log("check:pii — sin hallazgos (almacenamiento, console.* y autocompletado de campos con PII).");
