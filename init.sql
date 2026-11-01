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
