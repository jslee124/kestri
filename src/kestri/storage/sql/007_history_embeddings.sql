-- Rebuildable vectors only: no copied chat text and no logical-backup additions.
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM pg_available_extensions WHERE name='vector') THEN
  CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
  CREATE TABLE IF NOT EXISTS kestri.history_embeddings (
   owner_message_id bigint NOT NULL REFERENCES kestri.messages(id) ON DELETE CASCADE,
   chat_id bigint NOT NULL, source_hash text NOT NULL, embedding_space text NOT NULL,
   settings_generation integer NOT NULL, retrieval_generation integer NOT NULL,
   embedding public.vector(1024) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
   PRIMARY KEY(owner_message_id,embedding_space)
  );
 END IF;
END $$;
CREATE OR REPLACE FUNCTION kestri.invalidate_history_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF to_regclass('kestri.history_embeddings') IS NOT NULL THEN
  IF TG_OP!='INSERT' THEN
   DELETE FROM kestri.history_embeddings e USING kestri.messages m
   WHERE e.owner_message_id=m.id AND m.run_id=OLD.run_id;
  END IF;
  IF TG_OP!='DELETE' THEN
   DELETE FROM kestri.history_embeddings e USING kestri.messages m
   WHERE e.owner_message_id=m.id AND m.run_id=NEW.run_id;
  END IF;
 END IF;
 RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS kestri_history_source_sync ON kestri.messages;
CREATE TRIGGER kestri_history_source_sync AFTER INSERT OR UPDATE OR DELETE ON kestri.messages
FOR EACH ROW EXECUTE FUNCTION kestri.invalidate_history_source();
CREATE OR REPLACE FUNCTION kestri.invalidate_history_settings() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF to_regclass('kestri.history_embeddings') IS NOT NULL AND (
  NEW.auto_memory_enabled IS DISTINCT FROM OLD.auto_memory_enabled OR
  NEW.memory_use_enabled IS DISTINCT FROM OLD.memory_use_enabled OR
  NEW.memory_semantic_enabled IS DISTINCT FROM OLD.memory_semantic_enabled OR
  NEW.memory_embedding_space IS DISTINCT FROM OLD.memory_embedding_space OR
  NEW.memory_settings_generation IS DISTINCT FROM OLD.memory_settings_generation OR
  NEW.memory_retrieval_generation IS DISTINCT FROM OLD.memory_retrieval_generation OR
  NEW.automatic_history_floor IS DISTINCT FROM OLD.automatic_history_floor OR
  NEW.memory_activation_watermark IS DISTINCT FROM OLD.memory_activation_watermark
 ) THEN
  DELETE FROM kestri.history_embeddings WHERE chat_id=NEW.chat_id;
 END IF;
 RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS kestri_history_settings_sync ON kestri.conversations;
CREATE TRIGGER kestri_history_settings_sync AFTER UPDATE ON kestri.conversations
FOR EACH ROW EXECUTE FUNCTION kestri.invalidate_history_settings();
CREATE OR REPLACE FUNCTION kestri.invalidate_history_run() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.history_expired AND to_regclass('kestri.history_embeddings') IS NOT NULL THEN
  DELETE FROM kestri.history_embeddings e USING kestri.messages m
  WHERE e.owner_message_id=m.id AND m.run_id=NEW.id;
 END IF;
 RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS kestri_history_run_sync ON kestri.runs;
CREATE TRIGGER kestri_history_run_sync AFTER UPDATE OF history_expired ON kestri.runs
FOR EACH ROW EXECUTE FUNCTION kestri.invalidate_history_run();
INSERT INTO kestri.migrations(version) VALUES (7) ON CONFLICT DO NOTHING;
