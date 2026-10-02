ALTER TABLE kestri.conversations
    ADD COLUMN IF NOT EXISTS auto_memory_enabled boolean NOT NULL DEFAULT FALSE;

ALTER TABLE kestri.conversations
    ADD COLUMN IF NOT EXISTS memory_revision integer NOT NULL DEFAULT 0;

ALTER TABLE kestri.conversations
    ADD COLUMN IF NOT EXISTS memory_settings_generation integer NOT NULL DEFAULT 0;

ALTER TABLE kestri.conversations
    ADD COLUMN IF NOT EXISTS memory_activation_watermark bigint NOT NULL DEFAULT 0;

ALTER TABLE kestri.conversations
    ADD COLUMN IF NOT EXISTS automatic_history_floor bigint NOT NULL DEFAULT 0;

ALTER TABLE kestri.messages
    ADD COLUMN IF NOT EXISTS provenance text NOT NULL DEFAULT 'legacy';

ALTER TABLE kestri.memories
    ADD COLUMN IF NOT EXISTS category text NOT NULL DEFAULT 'background';

ALTER TABLE kestri.memories
    ADD COLUMN IF NOT EXISTS origin text NOT NULL DEFAULT 'explicit_command';

ALTER TABLE kestri.memories
    ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1;

ALTER TABLE kestri.memories
    ADD COLUMN IF NOT EXISTS fact_key text;

ALTER TABLE kestri.memories
    ADD COLUMN IF NOT EXISTS valid_from timestamptz;

ALTER TABLE kestri.memories
    ADD COLUMN IF NOT EXISTS review_after timestamptz;

ALTER TABLE kestri.memories
    ADD COLUMN IF NOT EXISTS last_source_message_id bigint;

ALTER TABLE kestri.memories
    DROP CONSTRAINT IF EXISTS memories_status_check;

ALTER TABLE kestri.memories
    ADD CONSTRAINT memories_status_check CHECK (status IN ('active', 'candidate',
    'superseded', 'forgotten', 'expired', 'quarantined'));

CREATE TABLE IF NOT EXISTS kestri.memory_jobs (
    id uuid PRIMARY KEY,
    chat_id bigint NOT NULL,
    source_message_id bigint REFERENCES kestri.messages (id) ON DELETE SET NULL,
    extractor_version text NOT NULL DEFAULT 'v1',
    settings_generation integer NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued',
    'running', 'retry_wait', 'succeeded', 'failed', 'cancelled')),
    run_id uuid REFERENCES kestri.runs (id),
    lease_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    captured_revision integer,
    captured_epoch integer,
    error_type text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_message_id, extractor_version)
);

CREATE INDEX IF NOT EXISTS kestri_memory_jobs_pending
    ON kestri.memory_jobs (chat_id, status, available_at);

CREATE TABLE IF NOT EXISTS kestri.memory_sources (
    memory_id uuid NOT NULL REFERENCES kestri.memories (id) DEFERRABLE,
    message_id bigint NOT NULL REFERENCES kestri.messages (id) ON DELETE CASCADE DEFERRABLE,
    quote text NOT NULL,
    start_offset integer NOT NULL,
    end_offset integer NOT NULL,
    PRIMARY KEY (memory_id, message_id),
    CHECK (start_offset >= 0 AND end_offset > start_offset)
);

CREATE TABLE IF NOT EXISTS kestri.memory_events (
    id bigserial PRIMARY KEY,
    chat_id bigint NOT NULL,
    memory_id uuid REFERENCES kestri.memories (id) DEFERRABLE,
    job_id uuid REFERENCES kestri.memory_jobs (id) DEFERRABLE,
    operation text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO kestri.migrations (version) VALUES (5) ON CONFLICT DO NOTHING;
