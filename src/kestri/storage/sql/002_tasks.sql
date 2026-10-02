CREATE TABLE IF NOT EXISTS kestri.tasks (
    id uuid PRIMARY KEY,
    chat_id bigint NOT NULL,
    title text NOT NULL,
    instructions text NOT NULL,
    timezone text NOT NULL,
    local_time text NOT NULL,
    weekdays integer[] NOT NULL,
    catch_up_seconds integer NOT NULL CHECK (catch_up_seconds BETWEEN 0 AND 86400),
    status text NOT NULL CHECK (status IN ('active', 'paused', 'deleted')),
    revision integer NOT NULL DEFAULT 1,
    next_due timestamptz NOT NULL,
    authorized_run_id uuid UNIQUE NOT NULL REFERENCES kestri.runs (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE kestri.runs
    ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'foreground';

ALTER TABLE kestri.runs
    ADD COLUMN IF NOT EXISTS task_id uuid REFERENCES kestri.tasks (id);

ALTER TABLE kestri.runs
    ADD COLUMN IF NOT EXISTS task_revision integer;

ALTER TABLE kestri.runs
    ADD COLUMN IF NOT EXISTS scheduled_for timestamptz;

ALTER TABLE kestri.runs
    ADD COLUMN IF NOT EXISTS available_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE kestri.runs
    ADD COLUMN IF NOT EXISTS attempt integer NOT NULL DEFAULT 1;

CREATE UNIQUE INDEX IF NOT EXISTS kestri_occurrence ON kestri.runs (task_id, scheduled_for);

ALTER TABLE kestri.messages
    ADD COLUMN IF NOT EXISTS task_id uuid REFERENCES kestri.tasks (id);

ALTER TABLE kestri.outbox
    ADD COLUMN IF NOT EXISTS task_id uuid REFERENCES kestri.tasks (id);

CREATE TABLE IF NOT EXISTS kestri.task_changes (
    run_id uuid PRIMARY KEY REFERENCES kestri.runs (id),
    task_id uuid REFERENCES kestri.tasks (id),
    action text NOT NULL,
    result text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO kestri.migrations (version) VALUES (2) ON CONFLICT DO NOTHING;
