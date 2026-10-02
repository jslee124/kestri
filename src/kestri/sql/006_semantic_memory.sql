ALTER TABLE kestri.conversations ADD COLUMN IF NOT EXISTS memory_use_enabled boolean NOT NULL DEFAULT true;
ALTER TABLE kestri.conversations ADD COLUMN IF NOT EXISTS memory_semantic_enabled boolean NOT NULL DEFAULT false;
ALTER TABLE kestri.conversations ADD COLUMN IF NOT EXISTS memory_retrieval_generation integer NOT NULL DEFAULT 0;
ALTER TABLE kestri.conversations ADD COLUMN IF NOT EXISTS memory_embedding_space text;
CREATE TABLE IF NOT EXISTS kestri.memory_index_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), chat_id bigint NOT NULL,
 memory_id uuid NOT NULL REFERENCES kestri.memories(id) DEFERRABLE,
 revision integer NOT NULL, content_hash text NOT NULL, embedding_space text NOT NULL,
 generation integer NOT NULL, status text NOT NULL DEFAULT 'queued'
 CHECK(status IN ('queued','running','retry_wait','succeeded','failed','cancelled')),
 run_id uuid REFERENCES kestri.runs(id), lease_token uuid, lease_until timestamptz,
 attempts integer NOT NULL DEFAULT 0, available_at timestamptz NOT NULL DEFAULT now(),
 error_type text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(memory_id,revision,embedding_space,generation)
);
CREATE INDEX IF NOT EXISTS kestri_index_jobs_pending ON kestri.memory_index_jobs(chat_id,status,available_at);
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM pg_available_extensions WHERE name='vector') THEN
  CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
  CREATE TABLE IF NOT EXISTS kestri.memory_embeddings (
   memory_id uuid NOT NULL REFERENCES kestri.memories(id) ON DELETE CASCADE,
   revision integer NOT NULL, content_hash text NOT NULL, embedding_space text NOT NULL,
   embedding public.vector(1024) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
   PRIMARY KEY(memory_id,embedding_space)
  );
 END IF;
END $$;
CREATE OR REPLACE FUNCTION kestri.sync_memory_index() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c kestri.conversations%ROWTYPE;
BEGIN
 IF to_regclass('kestri.memory_embeddings') IS NOT NULL THEN
  DELETE FROM kestri.memory_embeddings WHERE memory_id=NEW.id AND
    (NEW.status!='active' OR NEW.origin='auto_inferred' OR revision!=NEW.revision OR content_hash!=md5(NEW.content));
 END IF;
 UPDATE kestri.memory_index_jobs SET status='cancelled',lease_until=NULL,error_type='MemoryChanged',updated_at=now()
 WHERE memory_id=NEW.id AND status IN ('queued','running','retry_wait') AND
   (NEW.status!='active' OR NEW.origin='auto_inferred' OR revision!=NEW.revision OR content_hash!=md5(NEW.content));
 UPDATE kestri.runs SET status='cancelled',cancel_requested=true,finished_at=now()
 WHERE status='running' AND kind='memory_maintenance' AND id IN
  (SELECT run_id FROM kestri.memory_index_jobs WHERE memory_id=NEW.id AND status='cancelled');
 UPDATE kestri.usage SET state='unknown' WHERE state='reserved' AND run_id IN
  (SELECT run_id FROM kestri.memory_index_jobs WHERE memory_id=NEW.id AND status='cancelled');
 SELECT * INTO c FROM kestri.conversations WHERE chat_id=NEW.chat_id;
 IF NEW.status='active' AND NEW.origin!='auto_inferred' AND NEW.content!='' AND c.memory_use_enabled AND c.memory_semantic_enabled
 AND c.memory_embedding_space IS NOT NULL AND (NEW.expires_at IS NULL OR NEW.expires_at>now())
 AND (NEW.review_after IS NULL OR NEW.review_after>now())
 AND to_regclass('kestri.memory_embeddings') IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM kestri.memory_embeddings WHERE memory_id=NEW.id
   AND revision=NEW.revision AND content_hash=md5(NEW.content) AND embedding_space=c.memory_embedding_space) THEN
   INSERT INTO kestri.memory_index_jobs(chat_id,memory_id,revision,content_hash,embedding_space,generation)
   VALUES(NEW.chat_id,NEW.id,NEW.revision,md5(NEW.content),c.memory_embedding_space,c.memory_retrieval_generation)
   ON CONFLICT DO NOTHING;
  END IF;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS kestri_memory_index_sync ON kestri.memories;
CREATE TRIGGER kestri_memory_index_sync AFTER INSERT OR UPDATE ON kestri.memories
FOR EACH ROW EXECUTE FUNCTION kestri.sync_memory_index();
INSERT INTO kestri.migrations(version) VALUES (6) ON CONFLICT DO NOTHING;
