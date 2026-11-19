"""Auditoría inmutable: bloqueo de UPDATE/DELETE y cadena de hashes SHA-256 (S10-4, US-05).

La tabla registro_auditoria ya existe desde la 0010. Esta migración agrega:

- Trigger BEFORE UPDATE OR DELETE que rechaza la operación con un error claro (para todos
  los roles, también el dueño de la tabla) y trigger BEFORE TRUNCATE (los triggers de fila
  no se disparan con TRUNCATE).
- REVOKE explícito de UPDATE, DELETE y TRUNCATE para meditriage_app (y PUBLIC).
- Trigger BEFORE INSERT que calcula hash_anterior, hash_actual (SHA-256) y fecha_hora_evento
  dentro de la base: la aplicación no puede falsificarlos. Un lock de asesoría serializa los
  inserts para que la cadena no se bifurque.
- Función verificar_cadena_auditoria(): devuelve los registros cuya cadena está rota
  (vacía = íntegra).

Los registros que ya existían (solo los de /decision/fallo, hasheados desde Python) se
re-encadenan con la fórmula nueva ANTES de instalar el bloqueo; si la cadena no queda
íntegra, la migración falla.

El particionamiento anual del diseño queda solo documentado (docs/data/auditoria-inmutable.md).

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels = None
depends_on = None

APP_ROLE = "meditriage_app"


def upgrade() -> None:
    # Fórmula del hash: ver docs/data/auditoria-inmutable.md. Cambiarla rompe la cadena.
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION auditoria_calcular_hash(r registro_auditoria)
        RETURNS text LANGUAGE sql STABLE AS $$
            SELECT encode(sha256(convert_to(concat_ws('|',
                r.hash_anterior,
                r.registro_id::text,
                r.episodio_id::text,
                COALESCE(r.decision_id::text, ''),
                r.evento_tipo,
                r.usuario_id_actor::text,
                COALESCE(r.sugerencia_ia::text, ''),
                COALESCE(r.prompt_enviado, ''),
                COALESCE(r.decision_final::text, ''),
                r.hay_discrepancia::text,
                to_char(r.fecha_hora_evento, 'YYYY-MM-DD"T"HH24:MI:SS.US')
            ), 'UTF8')), 'hex')
        $$
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION verificar_cadena_auditoria()
        RETURNS TABLE (registro_id uuid, motivo text) LANGUAGE sql STABLE AS $$
            WITH ordenado AS (
                SELECT r AS fila,
                       lag(r.hash_actual) OVER (
                           ORDER BY r.fecha_hora_evento, r.registro_id
                       ) AS previo
                FROM registro_auditoria r
            )
            SELECT (o.fila).registro_id,
                   CASE
                       WHEN (o.fila).hash_anterior <> COALESCE(o.previo, repeat('0', 64))
                       THEN 'hash_anterior no coincide con el registro previo'
                       ELSE 'hash_actual no coincide con el contenido del registro'
                   END
            FROM ordenado o
            WHERE (o.fila).hash_anterior <> COALESCE(o.previo, repeat('0', 64))
               OR (o.fila).hash_actual <> auditoria_calcular_hash(o.fila)
        $$
        """
    )

    # Re-encadena lo que ya existía (aún sin el bloqueo instalado).
    op.execute(
        """
        DO $$
        DECLARE
            r registro_auditoria%ROWTYPE;
            previo text := repeat('0', 64);
            nuevo text;
        BEGIN
            FOR r IN SELECT * FROM registro_auditoria
                     ORDER BY fecha_hora_evento, registro_id LOOP
                r.hash_anterior := previo;
                nuevo := auditoria_calcular_hash(r);
                UPDATE registro_auditoria
                   SET hash_anterior = previo, hash_actual = nuevo
                 WHERE registro_id = r.registro_id;
                previo := nuevo;
            END LOOP;
            IF EXISTS (SELECT 1 FROM verificar_cadena_auditoria()) THEN
                RAISE EXCEPTION 'No se pudo re-encadenar registro_auditoria';
            END IF;
        END
        $$
        """
    )

    # Hash y fecha los pone la base, dentro del lock: la cadena sigue el orden real de inserción.
    # Lee el último registro con las políticas RLS de quien inserta (solo 'enfermero' inserta,
    # y ese rol también puede leer; ver 0010).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION auditoria_antes_de_insertar()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            ultimo registro_auditoria%ROWTYPE;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtext('registro_auditoria'));
            SELECT * INTO ultimo FROM registro_auditoria
             ORDER BY fecha_hora_evento DESC, registro_id DESC LIMIT 1;

            NEW.hash_anterior := COALESCE(ultimo.hash_actual, repeat('0', 64));
            NEW.fecha_hora_evento := GREATEST(
                clock_timestamp() AT TIME ZONE 'UTC',
                COALESCE(ultimo.fecha_hora_evento + interval '1 microsecond',
                         '-infinity'::timestamp)
            );
            NEW.hash_actual := auditoria_calcular_hash(NEW);
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_registro_auditoria_hash
        BEFORE INSERT ON registro_auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_antes_de_insertar()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auditoria_bloquear_modificacion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'registro_auditoria es append-only: no se permite % (inmutabilidad médico-legal, US-05)',
                TG_OP
                USING ERRCODE = '42501';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_registro_auditoria_inmutable
        BEFORE UPDATE OR DELETE ON registro_auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_bloquear_modificacion()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_registro_auditoria_no_truncate
        BEFORE TRUNCATE ON registro_auditoria
        FOR EACH STATEMENT EXECUTE FUNCTION auditoria_bloquear_modificacion()
        """
    )

    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON registro_auditoria FROM PUBLIC")
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON registro_auditoria FROM {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON registro_auditoria TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_registro_auditoria_no_truncate ON registro_auditoria")
    op.execute("DROP TRIGGER IF EXISTS trg_registro_auditoria_inmutable ON registro_auditoria")
    op.execute("DROP TRIGGER IF EXISTS trg_registro_auditoria_hash ON registro_auditoria")
    op.execute("DROP FUNCTION IF EXISTS auditoria_bloquear_modificacion()")
    op.execute("DROP FUNCTION IF EXISTS auditoria_antes_de_insertar()")
    op.execute("DROP FUNCTION IF EXISTS verificar_cadena_auditoria()")
    op.execute("DROP FUNCTION IF EXISTS auditoria_calcular_hash(registro_auditoria)")
