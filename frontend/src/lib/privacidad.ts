/**
 * Atributos para los campos que reciben datos personales (RUT, nombre, alergias...).
 * Evitan que el navegador los recuerde, los sugiera al siguiente paciente en un
 * equipo compartido o los envíe a un corrector ortográfico en la nube.
 */
export const CAMPO_PRIVADO = {
  autoComplete: "off",
  autoCorrect: "off",
  autoCapitalize: "off",
  spellCheck: false,
} as const;
