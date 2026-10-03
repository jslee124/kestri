ALTER TABLE kestri.runs ADD COLUMN IF NOT EXISTS media_group_id text;

CREATE UNIQUE INDEX IF NOT EXISTS kestri_runs_album
    ON kestri.runs (chat_id, media_group_id) WHERE media_group_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS kestri.image_inputs (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES kestri.runs (id),
    chat_id bigint NOT NULL,
    message_id bigint NOT NULL,
    file_id text NOT NULL,
    caption text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'ready', 'failed', 'expired')),
    mime_type text,
    width integer,
    height integer,
    byte_size integer,
    sha256 text,
    cleanup_pending boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (chat_id, message_id)
);

INSERT INTO kestri.migrations (version) VALUES (11) ON CONFLICT DO NOTHING;
