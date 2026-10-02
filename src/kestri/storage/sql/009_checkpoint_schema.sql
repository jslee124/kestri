-- LangGraph uses unqualified table names. Pin connections to public and preserve
-- installations where PostgreSQL's default $user search path chose kestri.
DO $$
DECLARE
    checkpoint_table text;
BEGIN
    FOREACH checkpoint_table IN ARRAY ARRAY[
        'checkpoint_migrations',
        'checkpoints',
        'checkpoint_blobs',
        'checkpoint_writes'
    ] LOOP
        IF to_regclass(format('kestri.%I', checkpoint_table)) IS NOT NULL THEN
            IF to_regclass(format('public.%I', checkpoint_table)) IS NOT NULL THEN
                RAISE EXCEPTION 'CheckpointSchemaConflict';
            END IF;
            EXECUTE format(
                'ALTER TABLE kestri.%I SET SCHEMA public',
                checkpoint_table
            );
        END IF;
    END LOOP;
END
$$;

INSERT INTO kestri.migrations (version) VALUES (9) ON CONFLICT DO NOTHING;
