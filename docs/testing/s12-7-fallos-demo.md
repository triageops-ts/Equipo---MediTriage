# S12-7 · Fallos encontrados antes de la demo

Una sola lista de los fallos anotados en las tarjetas S12-3 (flujo de enfermería), S12-4 (médico y auditor)
y S12-5 (tests con Postgres real), con un solo criterio: **si no rompe la demo, no se arregla ahora**.

| Clasificación | Significado |
|---|---|
| 🔴 Rompe la demo | Un paso del recorrido de la demo no se puede completar. Se arregla ahora, con un PR chico ligado a un Issue. |
| 🟡 Se ve mal | La demo se completa, pero algo puede confundir o verse poco profesional. Pasa a "Pendiente / Después". |
| ⚪ No importa | No se ve en la demo (entorno local, herramientas de desarrollo). Pasa a "Pendiente / Después". |

## Resultado

**Ningún fallo abierto rompe la demo.** El único que impedía un paso del recorrido (#3) ya está corregido.
El resto queda en "Pendiente / Después".

## Lista de fallos

| # | Origen | Fallo | Clasificación | Estado / decisión |
|---|---|---|---|---|
| 1 | S12-3 | Algunos pacientes no tienen fecha de nacimiento, y sin ella no se puede pedir la evaluación ESI (el backend responde 422 con un mensaje claro). | 🟡 Se ve mal | Pendiente / Después. Los pacientes de prueba sin fecha se cargaron directo en la base, sin pasar por el formulario. Pero el formulario también deja registrar sin fecha, así que en la demo hay que ingresarla siempre. Mitigación: el botón "Editar datos" (PR de edición de pacientes) permite completarla. |
| 2 | S12-3 | El modelo de IA no estuvo disponible; la sugerencia ESI salió del respaldo por reglas. | 🟡 Se ve mal | Pendiente / Después. Es el comportamiento diseñado: sin `ANTHROPIC_API_KEY` el motor usa `fallback-rule-engine` y la pantalla lo avisa. Ni el `docker-compose.yml` ni los manifiestos de `k8s/` configuran la clave. Mostrar Claude real en la demo es una decisión del equipo (clave, costo y Secret en staging). |
| 3 | S12-3 | Después de confirmar una decisión, la opción de sobrescribir el ESI quedaba deshabilitada. | 🔴 Rompía la demo | ✅ Arreglado. |
| 4 | S12-4 | — | — | Sin fallos: tablero médico en tiempo real con alertas, vista del auditor, marca de modificación manual y cadena de hashes válida (19 registros). |
| 5 | S12-5 | `pip install -r requirements.txt` fallaba en Windows por `uvloop`, y por eso tampoco se instalaba `pytest-bdd`. | ⚪ No importa | ✅ Arreglado (PR #101): `uvloop` solo se instala fuera de Windows. |
| 6 | S12-5 | En Windows, con `localhost` en `DATABASE_URL`, `test_us04_sala_espera` se quedaba colgado al conectar. | ⚪ No importa | Pendiente / Después. Solo afecta al correr los tests en Windows; se evita usando `127.0.0.1`. |
| 7 | S12-5 | Los tests de base de datos se saltan sin avisar si los usuarios demo están inactivos (la migración 0012 los desactiva). | ⚪ No importa | Pendiente / Después. Hay que reactivarlos después de migrar, igual que el CI. |
| 8 | S12-5 | `backend/.coverage` está versionado y aparece modificado cada vez que se corren los tests. | ⚪ No importa | Pendiente / Después. Sacarlo con `git rm --cached` y agregarlo al `.gitignore`. |
| 9 | Pruebas locales | Con Docker en Windows, el tablero del médico puede quedar en "Conectando…" si se entra por `127.0.0.1` (el WebSocket apunta a `localhost:8000`), y `localhost` puede fallar por IPv6 o HSTS del navegador. | ⚪ No importa | Pendiente / Después. Solo en local. En S12-4 el tiempo real funcionó. |
| 10 | Pruebas locales | El `docker-compose.yml` no pasa `ANTHROPIC_API_KEY` al backend y el backend no espera a que la base esté lista. | ⚪ No importa | Pendiente / Después. Solo en local; se arregla volviendo a levantar el backend. |

## Verificación (tarea 3)

Después de los arreglos se repiten los recorridos de S12-3 (enfermería) y S12-4 (médico y auditor), **en el
mismo ambiente donde se hará la demo** (staging), registrando fecha, ambiente y resultado:

| Recorrido | Ambiente | Fecha | Resultado |
|---|---|---|---|
| S12-3 · Enfermería | Local (Docker, http://127.0.0.1:3000) | 26/11/2026 | |
| S12-4 · Médico y auditor | Local (Docker, http://127.0.0.1:3000) | 26/11/2026 | |
