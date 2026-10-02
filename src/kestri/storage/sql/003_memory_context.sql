ALTER TABLE kestri.conversations
    ADD COLUMN IF NOT EXISTS memory_epoch integer NOT NULL DEFAULT 0;

ALTER TABLE kestri.runs
    ADD COLUMN IF NOT EXISTS memory_epoch integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS kestri.memories (
    id uuid PRIMARY KEY,
    chat_id bigint NOT NULL,
    content text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('global', 'task')),
    task_id uuid REFERENCES kestri.tasks (id),
    source_message_id bigint NOT NULL,
    source_run_id uuid NOT NULL REFERENCES kestri.runs (id),
    status text NOT NULL CHECK (status IN ('active', 'superseded', 'forgotten', 'expired')),
    supersedes uuid REFERENCES kestri.memories (id),
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((scope = 'global' AND task_id IS NULL) OR (scope = 'task' AND task_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS kestri.memory_changes (
    run_id uuid PRIMARY KEY REFERENCES kestri.runs (id),
    result text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS kestri_memory_active ON kestri.memories (chat_id, status);

INSERT INTO kestri.migrations (version) VALUES (3) ON CONFLICT DO NOTHING;
