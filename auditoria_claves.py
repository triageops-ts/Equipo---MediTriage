import psycopg

# 1. Leer el archivo .env manualmente
env_vars = {}
with open(".env", "r") as f:
    for line in f:
        if "=" in line and not line.strip().startswith("#"):
            key, val = line.strip().split("=", 1)
            env_vars[key] = val

db_url = env_vars.get("DATABASE_URL")
clave = env_vars.get("APP_ENCRYPTION_KEY")

exitos = 0
fallos = 0

print(f"Auditando BD con la clave: {clave}")

# 2. autocommit=True evita que un error bloquee toda la conexión
with psycopg.connect(db_url, autocommit=True) as conn:
    with conn.cursor() as cur:
        # CORRECCIÓN: Solo pedimos la columna rut
        cur.execute("SELECT rut FROM paciente;")
        pacientes = cur.fetchall()
        
        for paciente in pacientes:
            rut_cifrado = paciente[0] # Ahora el rut es el índice 0
            try:
                # Intenta descifrar cada RUT individualmente
                cur.execute("SELECT pgp_sym_decrypt(%s::bytea, %s);", (rut_cifrado, clave))
                exitos += 1
            except Exception:
                fallos += 1

print("-" * 30)
print(f"✅ Descifrados con éxito: {exitos}")
print(f"❌ Fallos (clave incorrecta): {fallos}")