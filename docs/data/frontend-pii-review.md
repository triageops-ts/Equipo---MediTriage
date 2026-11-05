# Revisión de PII en el navegador (frontend) — Tarjeta S06-5

**Alcance:** pantalla de enfermería (`/nurse`): buscador de paciente, formulario clínico, anamnesis y llamadas a la API.
**Pregunta de la tarjeta:** ¿el formulario deja PII en `localStorage` o en el estado del navegador más tiempo del necesario?
**Datos personales que maneja la pantalla:** RUT, nombre, fecha de nacimiento, sexo, alergias y anamnesis (texto libre). Ver `clasificacion_pii.md`.

## Conclusión

- **`localStorage`: nunca se usó.** Tampoco `sessionStorage`, IndexedDB, cookies ni Cache API.
- En el "estado del navegador" había **4 puntos donde la PII podía quedar de más**. Se corrigieron (tabla siguiente).
- Queda **1 pendiente que necesita decisión del equipo** (el RUT viaja en la URL de la búsqueda, ver abajo).

## Qué se revisó y cómo quedó

| Dónde podía quedar PII | Antes | Ahora |
|---|---|---|
| `localStorage`, `sessionStorage`, IndexedDB, cookies, Cache API | No se usan | Igual. `npm run check:pii` falla si alguien los agrega |
| Autocompletado e historial de formularios del navegador | Los campos RUT, nombre, nacimiento, alergias y anamnesis no lo desactivaban: en un equipo compartido el navegador podía sugerir el RUT del paciente anterior | `autoComplete="off"` en los 5 campos; además sin corrector ortográfico en RUT, nombre y alergias (`lib/privacidad.ts`) |
| Memoria de la página tras registrar el ingreso | El paciente, el RUT, las alergias y la anamnesis seguían en pantalla hasta pulsar "Nuevo ingreso" | Se borran apenas el servidor confirma el ingreso |
| Botón "Atrás" (el navegador restaura la página tal cual estaba: bfcache) | Volvía a aparecer el paciente anterior con todos sus datos | Al restaurar la página se borra todo (`pageshow` con `persisted`) |
| Caché HTTP del navegador | Las respuestas de `GET /patients?rut=` y `POST /patients` no pedían "no guardar" | Todas las llamadas usan `cache: "no-store"` |
| URL de la página y consola del navegador | No llevan PII | Igual. `check:pii` falla si aparece un `console.*` sin marcar |
| Fuentes y terceros | Las fuentes Geist se descargan al compilar y se sirven desde el mismo dominio; no hay analítica ni scripts externos | Igual |

## Pendientes (no se cambiaron, necesitan decisión)

1. **El RUT va en la URL:** la búsqueda es `GET /api/v1/patients?rut=...`. Las URL quedan en los registros de proxies, balanceadores y del hosting. Propuesta: buscar con `POST /patients/search` (el RUT en el cuerpo). Implica cambiar `api/openapi.yaml` y el backend. El log de la API ya no registra la query string.
2. **Cuando exista el login:** el JWT no debe guardarse en `localStorage` ni `sessionStorage`; usar cookie `HttpOnly`, `Secure` y `SameSite`.
3. **Bloqueo por inactividad:** en una estación compartida, borrar el formulario tras unos minutos sin uso (propuesta: 10 a 15 min).
4. **Anamnesis:** es texto libre y puede contener nombres. Se dejó el corrector del navegador activo para no entorpecer la escritura clínica.
5. **Error 409 al registrar un paciente:** el mensaje del backend incluye el RUT y se muestra en pantalla. Solo vive en pantalla y se borra al reiniciar el buscador.

## Cómo volver a comprobarlo

1. `cd frontend && npm run check:pii` debe terminar sin hallazgos.
2. A mano, en el navegador (DevTools > Application): después de buscar un paciente y registrar un ingreso, **Local storage, Session storage, IndexedDB y Cookies** deben estar vacíos.
3. Registra un ingreso, sal a otra página y vuelve con "Atrás": el formulario debe aparecer vacío.
