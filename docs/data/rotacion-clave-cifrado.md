# Rotación de la clave de cifrado (`APP_ENCRYPTION_KEY`)

## Estado actual
- Hay una **clave oficial por entorno** (local, Neon, Kubernetes), guardada en el
  gestor de contraseñas del equipo y, en Kubernetes, en el Secret `triageops-secrets`.
- Verificación del 15-11-2026 en Neon: la clave oficial descifra el 100 % de los
  datos cifrados (`paciente.rut`: 15/15, `contacto_paciente`: 1/1). Los 15 RUT
  tienen el formato normal de `pgp_sym_encrypt` (empiezan con `c30d`).
- Huella para comparar la clave sin revelarla: largo 19 y SHA-256 (8 primeros
  caracteres) `eab383e1`.
- `usuario_staff.rut` y `usuario_staff.email` están vacíos (NULL) por ahora.

## Qué datos usan esta clave
`paciente.rut`, `contacto_paciente.direccion | telefono | email` y
`usuario_staff.rut | email`, todos cifrados con `pgp_sym_encrypt`.

## Cómo verificar la clave sin compartirla
Cada integrante ejecuta, con su clave cargada en la sesión:

```powershell
python -c "import hashlib,os; k=os.environ.get('APP_ENCRYPTION_KEY',''); print(len(k), hashlib.sha256(k.encode()).hexdigest()[:8])"
```
Debe dar `19 eab383e1`. Otro largo suele indicar espacios o comillas de más en el `.env`.

## Cuándo rotar
- Sospecha de fuga o salida de una persona con acceso a la clave.
- Reemplazar la clave de prueba actual por una clave fuerte.

## Procedimiento de rotación
1. Crear una rama de respaldo en Neon (Create branch, con datos y esquema).
2. Generar la clave nueva:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`
3. Re-cifrar todo en **una sola transacción** (si algo falla, no cambia nada).
   Ejecutar desde `backend/` con `OLD_KEY` y `NEW_KEY` definidas solo en la
   sesión (nunca en el editor SQL de Neon, para que no queden en su historial):

   ```python
   import os, psycopg
   from dotenv import load_dotenv

   load_dotenv()
   url, old, new = os.environ["DATABASE_URL"], os.environ["OLD_KEY"], os.environ["NEW_KEY"]
   COLS = [("paciente", "rut"),
           ("contacto_paciente", "direccion"),
           ("contacto_paciente", "telefono"),
           ("contacto_paciente", "email"),
           ("usuario_staff", "rut"),
           ("usuario_staff", "email")]

   with psycopg.connect(url) as conn, conn.cursor() as cur:
       for t, c in COLS:
           cur.execute(
               f"UPDATE {t} SET {c} = pgp_sym_encrypt(pgp_sym_decrypt({c}, %s::text), "
               f"%s::text, 'cipher-algo=aes256') WHERE {c} IS NOT NULL", (old, new))
           print(f"{t}.{c}: {cur.rowcount} filas")
       # Reemplaza también la fila canario del chequeo de arranque:
       cur.execute(
           "UPDATE clave_canario SET valor = pgp_sym_encrypt(%s::text, %s::text, "
           "'cipher-algo=aes256') WHERE id = 1", ("meditriage-canario-v1", new))
       # Verificación: si algo no descifra con la clave nueva, se revierte todo.
       for t, c in COLS:
           cur.execute(f"SELECT count(pgp_sym_decrypt({c}, %s::text)) FROM {t} "
                       f"WHERE {c} IS NOT NULL", (new,))
           print("verificadas", t, c, cur.fetchone()[0])
   ```
4. Actualizar la clave **a la vez** en el gestor de contraseñas, en el `.env` de
   cada integrante y en el Secret de Kubernetes. Reiniciar los pods.
5. Comprobar que el backend arranca: el chequeo de arranque con la fila canario
   lo verifica y se niega a iniciar si la clave no coincide.

## Si se pierde la clave
No se puede reconstruir. Si los datos son sintéticos, se borran solo en la base
de pruebas (con una rama de respaldo antes) y se recrean con la clave oficial.
Nunca se borra `registro_auditoria`.

## `rut_hash`
La columna `paciente.rut_hash` guarda el HMAC-SHA256 del RUT normalizado, con la
clave aparte `APP_RUT_HASH_KEY`. Al rotar `APP_ENCRYPTION_KEY` **no** hay que
recalcularlo. Solo se recalcula si cambia `APP_RUT_HASH_KEY`:

```sql
UPDATE paciente
SET rut_hash = encode(hmac(pgp_sym_decrypt(rut, '<clave de cifrado>'),
                           '<clave del hash>', 'sha256'), 'hex')
WHERE rut IS NOT NULL;
```
(Ejecutarlo desde un script, no desde el editor SQL, por la misma razón de arriba.)

## Notas
- `backend/migrations/db.py` era una copia idéntica de `backend/app/db.py` que
  nadie importaba; se eliminó.
- Las tablas `clave_canario` y la columna `rut_hash` existen una vez aplicadas las
  migraciones 0006 y 0007.

## Kubernetes
- El Secret `triageops-secrets` (namespace `triageops-dev`) lo crea Terraform; Argo CD no lo administra.
- Lleva `APP_ENCRYPTION_KEY` y `APP_RUT_HASH_KEY`, claves propias de Kubernetes (distintas de las de Neon), guardadas en el gestor de contraseñas del equipo.
- Se agregaron con `kubectl patch ... --patch-file`. Un `terraform apply` posterior rehace el Secret y borra estas claves: hay que volver a agregarlas.
- `triageops-prod` aún no existe en el cluster local; al crearlo, repetir lo mismo.