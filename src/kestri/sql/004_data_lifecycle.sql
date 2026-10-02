ALTER TABLE kestri.runs ADD COLUMN IF NOT EXISTS history_expired boolean NOT NULL DEFAULT false;
ALTER TABLE kestri.tasks ADD COLUMN IF NOT EXISTS restored boolean NOT NULL DEFAULT false;
ALTER TABLE kestri.memories DROP CONSTRAINT IF EXISTS memories_status_check;
ALTER TABLE kestri.memories ADD CONSTRAINT memories_status_check
 CHECK(status IN ('active','superseded','forgotten','expired','quarantined'));
ALTER TABLE kestri.tasks ALTER CONSTRAINT tasks_authorized_run_id_fkey DEFERRABLE;
ALTER TABLE kestri.runs ALTER CONSTRAINT runs_task_id_fkey DEFERRABLE;
ALTER TABLE kestri.memories ALTER CONSTRAINT memories_supersedes_fkey DEFERRABLE;
INSERT INTO kestri.migrations(version) VALUES (4) ON CONFLICT DO NOTHING;
