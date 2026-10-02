CREATE TABLE IF NOT EXISTS kestri.history_index_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    chat_id bigint NOT NULL,
    owner_message_id bigint REFERENCES kestri.messages (id) ON DELETE SET NULL DEFERRABLE,
    settings_generation integer NOT NULL,
    retrieval_generation integer NOT NULL,
    embedding_space text NOT NULL,
    source_revision integer NOT NULL DEFAULT 1,
    source_hash text,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running',
    'retry_wait', 'succeeded', 'failed', 'cancelled')),
    run_id uuid REFERENCES kestri.runs (id),
    lease_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    error_type text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_message_id, settings_generation, retrieval_generation)
);

CREATE INDEX IF NOT EXISTS kestri_history_jobs_pending ON kestri.history_index_jobs (chat_id,
    status, available_at);

CREATE OR REPLACE FUNCTION kestri.queue_history_turn (
    owner_id bigint,
    allow_enqueue boolean DEFAULT TRUE
)
    RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    source_message kestri.messages%ROWTYPE;
    conversation kestri.conversations%ROWTYPE;
BEGIN
    IF owner_id IS NULL THEN
        RETURN;
    END IF;
    -- Revoke the previous source version before scheduling its replacement.
    UPDATE
        kestri.history_index_jobs
    SET
        status = 'cancelled',
        lease_until = NULL,
        error_type = 'SourceChanged',
        updated_at = now()
    WHERE
        owner_message_id = owner_id
        AND status IN ('queued', 'running', 'retry_wait');
    UPDATE
        kestri.runs
    SET
        status = 'cancelled',
        cancel_requested = TRUE,
        finished_at = now()
    WHERE
        status = 'running'
        AND id IN (
            SELECT
                run_id
            FROM
                kestri.history_index_jobs
            WHERE
                owner_message_id = owner_id
                AND status = 'cancelled');
    -- Submitted requests can have unknown costs after cancellation.
    UPDATE
        kestri.usage
    SET
        state = 'unknown'
    WHERE
        state = 'reserved'
        AND run_id IN (
            SELECT
                run_id
            FROM
                kestri.history_index_jobs
            WHERE
                owner_message_id = owner_id
                AND status = 'cancelled');
    SELECT
        *
    INTO
        source_message
    FROM
        kestri.messages
    WHERE
        id = owner_id;
    SELECT
        *
    INTO
        conversation
    FROM
        kestri.conversations
    WHERE
        chat_id = source_message.chat_id;
    -- The consent watermark excludes all pre-activation source messages.
    IF allow_enqueue
        AND source_message.direction = 'in'
        AND source_message.provenance = 'direct'
        AND conversation.auto_memory_enabled
        AND conversation.memory_use_enabled
        AND conversation.memory_semantic_enabled
        AND conversation.memory_embedding_space IS NOT NULL
        AND source_message.id > GREATEST(
            conversation.memory_activation_watermark,
            conversation.automatic_history_floor
        )
        AND to_regclass('kestri.history_embeddings') IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM kestri.runs
            WHERE id = source_message.run_id
                AND kind = 'foreground'
                AND NOT history_expired
        )
        AND (
            source_message.task_id IS NULL
            OR EXISTS (
                SELECT 1
                FROM kestri.tasks
                WHERE id = source_message.task_id AND status != 'deleted'
            )
        )
    THEN
        INSERT INTO kestri.history_index_jobs (
            chat_id,
            owner_message_id,
            settings_generation,
            retrieval_generation,
            embedding_space)
        VALUES (
            source_message.chat_id,
            source_message.id,
            conversation.memory_settings_generation,
            conversation.memory_retrieval_generation,
            conversation.memory_embedding_space)
        ON CONFLICT (
            owner_message_id,
            settings_generation,
            retrieval_generation)
            DO UPDATE SET
                status = 'queued',
                source_revision = kestri.history_index_jobs.source_revision + 1,
                source_hash = NULL,
                run_id = NULL,
                lease_token = NULL,
                lease_until = NULL,
                attempts = 0,
                available_at = now(),
                error_type = NULL,
                updated_at = now();
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION kestri.sync_history_job_source ()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $$
DECLARE
    owner_id bigint;
    source_run uuid;
BEGIN
    source_run := CASE WHEN TG_OP = 'DELETE' THEN
        OLD.run_id
    ELSE
        NEW.run_id
    END;
    SELECT
        id
    INTO
        owner_id
    FROM
        kestri.messages
    WHERE
        run_id = source_run
        AND direction = 'in'
        AND provenance = 'direct'
    ORDER BY
        id
    LIMIT 1;
    IF TG_OP = 'DELETE' AND OLD.direction = 'in' THEN
        owner_id := OLD.id;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.direction = 'in' THEN
        owner_id := OLD.id;
    END IF;
    PERFORM
        kestri.queue_history_turn (owner_id, NOT (TG_OP = 'DELETE'
                AND OLD.direction = 'in'));
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS kestri_history_job_source ON kestri.messages;

CREATE TRIGGER kestri_history_job_source
    BEFORE DELETE ON kestri.messages
    FOR EACH ROW
    EXECUTE FUNCTION kestri.sync_history_job_source ();

DROP TRIGGER IF EXISTS kestri_history_job_accept ON kestri.messages;

CREATE TRIGGER kestri_history_job_accept
    AFTER INSERT OR UPDATE ON kestri.messages
    FOR EACH ROW
    EXECUTE FUNCTION kestri.sync_history_job_source ();

CREATE OR REPLACE FUNCTION kestri.sync_history_job_settings ()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.auto_memory_enabled IS DISTINCT FROM OLD.auto_memory_enabled
        OR NEW.memory_use_enabled IS DISTINCT FROM OLD.memory_use_enabled
        OR NEW.memory_semantic_enabled IS DISTINCT FROM OLD.memory_semantic_enabled
        OR NEW.memory_embedding_space IS DISTINCT FROM OLD.memory_embedding_space
        OR NEW.memory_settings_generation IS DISTINCT FROM OLD.memory_settings_generation
        OR NEW.memory_retrieval_generation IS DISTINCT FROM OLD.memory_retrieval_generation
        OR NEW.automatic_history_floor IS DISTINCT FROM OLD.automatic_history_floor
        OR NEW.memory_activation_watermark IS DISTINCT FROM OLD.memory_activation_watermark
    THEN
        UPDATE
            kestri.history_index_jobs
        SET
            status = 'cancelled',
            lease_until = NULL,
            error_type = 'SettingsChanged',
            updated_at = now()
        WHERE
            chat_id = NEW.chat_id
            AND status IN ('queued', 'running', 'retry_wait');
        UPDATE
            kestri.runs
        SET
            status = 'cancelled',
            cancel_requested = TRUE,
            finished_at = now()
        WHERE
            status = 'running'
            AND id IN (
                SELECT
                    run_id
                FROM
                    kestri.history_index_jobs
                WHERE
                    chat_id = NEW.chat_id
                    AND status = 'cancelled');
        UPDATE
            kestri.usage
        SET
            state = 'unknown'
        WHERE
            state = 'reserved'
            AND run_id IN (
                SELECT
                    run_id
                FROM
                    kestri.history_index_jobs
                WHERE
                    chat_id = NEW.chat_id
                    AND status = 'cancelled');
        IF NEW.auto_memory_enabled
            AND NEW.memory_use_enabled
            AND NEW.memory_semantic_enabled
            AND NEW.memory_embedding_space IS NOT NULL
            AND to_regclass('kestri.history_embeddings') IS NOT NULL
        THEN
            INSERT INTO kestri.history_index_jobs (
                chat_id,
                owner_message_id,
                settings_generation,
                retrieval_generation,
                embedding_space)
            SELECT
                m.chat_id,
                m.id,
                NEW.memory_settings_generation,
                NEW.memory_retrieval_generation,
                NEW.memory_embedding_space
            FROM
                kestri.messages m
                JOIN kestri.runs r ON r.id = m.run_id
                LEFT JOIN kestri.tasks t ON t.id = m.task_id
            WHERE
                m.chat_id = NEW.chat_id
                AND m.direction = 'in'
                AND m.provenance = 'direct'
                AND r.kind = 'foreground'
                AND NOT r.history_expired
                AND m.id > GREATEST (NEW.memory_activation_watermark, NEW.automatic_history_floor)
                AND (m.task_id IS NULL
                    OR t.status != 'deleted')
            ON CONFLICT
                DO NOTHING;
        END IF;
    END IF;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS kestri_history_job_settings ON kestri.conversations;

CREATE TRIGGER kestri_history_job_settings
    AFTER UPDATE ON kestri.conversations
    FOR EACH ROW
    EXECUTE FUNCTION kestri.sync_history_job_settings ();

CREATE OR REPLACE FUNCTION kestri.sync_history_job_run ()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $$
DECLARE
    owner_id bigint;
BEGIN
    IF NEW.history_expired THEN
        FOR owner_id IN
        SELECT
            id
        FROM
            kestri.messages
        WHERE
            run_id = NEW.id
            AND direction = 'in' LOOP
                PERFORM
                    kestri.queue_history_turn (owner_id);
            END LOOP;
    END IF;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS kestri_history_job_run ON kestri.runs;

CREATE TRIGGER kestri_history_job_run
    AFTER UPDATE OF history_expired ON kestri.runs
    FOR EACH ROW
    EXECUTE FUNCTION kestri.sync_history_job_run ();

-- Upgrade registers only already-opted-in direct sources, never pre-activation history.
INSERT INTO kestri.history_index_jobs (
    chat_id,
    owner_message_id,
    settings_generation,
    retrieval_generation,
    embedding_space)
SELECT
    m.chat_id,
    m.id,
    c.memory_settings_generation,
    c.memory_retrieval_generation,
    c.memory_embedding_space
FROM
    kestri.messages m
    JOIN kestri.conversations c ON c.chat_id = m.chat_id
    JOIN kestri.runs r ON r.id = m.run_id
    LEFT JOIN kestri.tasks t ON t.id = m.task_id
WHERE
    c.auto_memory_enabled
    AND c.memory_use_enabled
    AND c.memory_semantic_enabled
    AND c.memory_embedding_space IS NOT NULL
    AND to_regclass('kestri.history_embeddings') IS NOT NULL
    AND m.direction = 'in'
    AND m.provenance = 'direct'
    AND r.kind = 'foreground'
    AND NOT r.history_expired
    AND m.id > GREATEST (c.memory_activation_watermark, c.automatic_history_floor)
    AND (m.task_id IS NULL
        OR t.status != 'deleted')
ON CONFLICT
    DO NOTHING;

INSERT INTO kestri.migrations (version) VALUES (8) ON CONFLICT DO NOTHING;
