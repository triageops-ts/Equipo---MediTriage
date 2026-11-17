-- Habilitar la extensión pgcrypto desde el arranque
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Crear una tabla base temporal para activar la política
CREATE TABLE IF NOT EXISTS pacientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(100)
);

-- Configurar las políticas base de Row-Level Security (RLS)
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
CREATE POLICY politicas_base_pacientes ON pacientes FOR ALL USING (false);


-- Rol de la app para desarrollo local (la migración 0008 le da los permisos).
-- Esta contraseña es solo para el Postgres local de Docker, no para Neon.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'meditriage_app') THEN
        CREATE ROLE meditriage_app LOGIN PASSWORD 'meditriage_app_dev' NOBYPASSRLS;
    END IF;
END
$$;