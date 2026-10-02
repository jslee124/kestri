CREATE SCHEMA IF NOT EXISTS kestri;

CREATE TABLE IF NOT EXISTS kestri.migrations (
    version integer PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS kestri.meta (
    key text PRIMARY KEY,
    value jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS kestri.conversations (
    chat_id bigint PRIMARY KEY,
    thread_id text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kestri.runs (
    id uuid PRIMARY KEY,
    chat_id bigint NOT NULL,
    message_id bigint NOT NULL,
    request text NOT NULL,
    reply_to bigint,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'completed',
    'failed', 'cancelled', 'interrupted')),
    cancel_requested boolean NOT NULL DEFAULT FALSE,
    source_thread text,
    result text,
    error_type text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS kestri_runs_queue ON kestri.runs (status, created_at);

CREATE TABLE IF NOT EXISTS kestri.inbox (
    update_id bigint PRIMARY KEY,
    chat_id bigint NOT NULL,
    message_id bigint NOT NULL,
    run_id uuid REFERENCES kestri.runs (id),
    accepted_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kestri.messages (
    id bigserial PRIMARY KEY,
    chat_id bigint NOT NULL,
    telegram_id bigint,
    direction text NOT NULL CHECK (direction IN ('in', 'out')),
    content text NOT NULL,
    reply_to bigint,
    run_id uuid REFERENCES kestri.runs (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (chat_id, direction, telegram_id)
);

CREATE TABLE IF NOT EXISTS kestri.outbox (
    sequence bigserial
        UNIQUE,
        id uuid PRIMARY KEY,
        chat_id bigint NOT NULL,
        reply_to bigint,
        run_id uuid REFERENCES kestri.runs (id),
        content text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending',
        'sending', 'sent', 'failed', 'uncertain')),
        attempts integer NOT NULL DEFAULT 0,
        error_type text,
        next_attempt timestamptz NOT NULL DEFAULT now(),
        created_at timestamptz NOT NULL DEFAULT now(),
        telegram_id bigint
);

CREATE INDEX IF NOT EXISTS kestri_outbox_pending ON kestri.outbox (status, next_attempt);

CREATE TABLE IF NOT EXISTS kestri.evidence (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES kestri.runs (id),
    kind text NOT NULL,
    url text NOT NULL,
    title text NOT NULL,
    status text NOT NULL,
    truncated boolean NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kestri.usage (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES kestri.runs (id),
    kind text NOT NULL,
    amount_micro_usd bigint NOT NULL CHECK (amount_micro_usd >= 0),
    state text NOT NULL DEFAULT 'reserved',
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO kestri.migrations (version) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS kestri.events (
    sequence bigserial
        PRIMARY KEY,
        run_id uuid REFERENCES kestri.runs (id),
        kind text NOT NULL,
        metadata jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
);
