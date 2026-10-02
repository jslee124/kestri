# Data lifecycle reference

[简体中文](data-lifecycle.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02.

See [data maintenance internals](../design/data-maintenance.md) for snapshot fields, validation order, restore transformations, cleanup algorithms, and failure boundaries.

## Local operator interface

`kestri data` uses `DATABASE_URL`, `KESTRI_TELEGRAM_OWNER_ID`, and `KESTRI_WORKSPACE_DIR`; provider credentials are unnecessary. These commands are operator controls, never model tools or Telegram commands. Stop the app for backup, export, restore, and manual maintenance. A database advisory lease rejects an operator while the matching bot is running. Status remains available while running.

| Command | Effect |
| --- | --- |
| `data status` | Counts and the last maintenance outcome; no message bodies |
| `data backup [PATH]` | Private logical backup including referenced retrieved evidence; defaults to `/workspace/backups/UUID.json` in Compose |
| `data export PATH` | Private business-record export without evidence text; not restorable |
| `data restore PATH [--apply]` | Validate by default; apply only to an empty database/workspace with the same owner |
| `data cleanup [--apply]` | Preview/apply retention |
| `data delete-history [--before ISO] [--apply]` | Clear archive content before a timezone-aware cutoff, or all current history by default |
| `data erase [--apply]` | Clear local content, forget memory, delete task agreements, and prune managed backups; retain minimal operational markers |

Files are created exclusively with POSIX mode `0600`; existing paths are not overwritten. Private JSON is **unencrypted** and contains personal data. Restore rejects symlinks, nonregular/world-readable files, wrong format/schema/owner/columns, checksum errors, invalid evidence IDs, and nonempty targets. SHA-256 detects corruption; it does not authenticate an untrusted author. Only restore trusted owner-created bundles. Maximum bundle size is 64 MiB and 50,000 rows; creation also has a conservative 32 MiB content allowance. Larger installations need another reviewed backup solution.

## Retention and deletion

| Setting | Default | Range |
| --- | --- | --- |
| `KESTRI_ARCHIVE_RETENTION_DAYS` | 90 | 1–3650 days |
| `KESTRI_EVIDENCE_RETENTION_DAYS` | 30 | 1–3650 days |
| `KESTRI_LOG_RETENTION_DAYS` | 30 | 1–3650 days |
| `KESTRI_BACKUP_RETENTION_DAYS` | 30 | 1–3650 days |
| `KESTRI_MAINTENANCE_INTERVAL_SECONDS` | 3600 | 60–86400 seconds |

Maintenance runs on startup and at the configured interval. It defers when a run is queued/running or a delivery pending/sending. It locks conversation rows while changing content. Continually busy installations can postpone cleanup; inspect status and stop the app for manual cleanup if necessary.

Archive expiration deletes canonical messages and clears run requests/results, outbox bodies, and old mutation acknowledgement text. Forgotten/superseded memory content and deleted task text are cleared after their retention cutoff. Active and quarantined memory and nondeleted task agreements have separate durable retention intent. Temporary evidence is marked expired before physical unlink; failed unlink remains pending for a later retry and is unavailable for retrieval. Detailed events expire independently. Clearing archive/evidence also resets conversation heads/epochs and removes all stored graph checkpoints, blobs, and writes while idle, preventing retained summaries from reviving removed data. This favors revocation over continuity.

IDs, identity binding, deduplication/revocation markers, timing/status, and cost ledgers remain. `erase` is content erasure, not a database/volume wipe, and does not reset spending allowances. No separate pinned-result interface exists: archived answers follow archive retention; their raw pages follow evidence retention. Empty run directories may remain after retention unlink.

Only valid UUID-named backup bundles inside the workspace `backups` directory are managed; expiration uses file modification time. Custom paths, external copies, exports, credentials, Telegram messages, and provider-side records are outside local cleanup. Managed backups expire separately from active records, so forgotten content may remain in a private backup until expiration. Keep off-device copies and enforce their retention yourself.

## Conservative restore

Format `kestri-data-v1`, schema 6, includes business tables and retrieved evidence text, and excludes LangGraph checkpoints/internal reasoning and credentials. It is a logical application snapshot, not `pg_dump` or a full crash-state image. Schema changes require an explicit migration/compatibility decision.

Restore quarantines **every imported active memory**, pauses **every imported nondeleted task**, resets foreground context, interrupts queued/running work, marks pending/sending deliveries uncertain, and converts unresolved usage reservations to unknown. Already deleted/forgotten records remain inactive. `/memory` shows quarantined facts with a warning; re-enter an intended fact with `/remember`. `/tasks` warns about imported tasks; explicitly resume only a currently intended agreement. Old backups cannot silently reinstate later-revoked authority.

On the first Telegram startup after restore, the app discards updates pending at that boundary and emits a recovery notice. Send new instructions after that notice. This prevents stale commands from reauthorizing restored data. Ordinary restarts do not discard pending updates. The boundary uses the documented negative-offset behavior of [Telegram getUpdates](https://core.telegram.org/bots/api#getupdates), checked 2026-10-02.

Controlled restore failures roll back database changes and remove newly created evidence. Abrupt process/power loss during file work can leave orphan files; keep the source backup and retry into a fresh empty target after inspection. Do not claim atomic recovery at every crash point. See [backup and restore](../how-to/backup-and-restore.md) and [ADR-0006](../decisions/0006-conservative-data-recovery.md).

## Automatic-memory lifecycle

Schema 5 includes `memory_jobs`, `memory_sources` and `memory_events`; schema 4 restore inserts conservative new-column defaults and empty new tables. Restore always disables extraction, increments settings generation, cancels jobs and quarantines both active and candidate memories. It never schedules embedding or extraction from restored text. Archive source deletion cascades quote removal, expires dependent automatic active/candidate facts, cancels affected jobs and invalidates context. Erase also removes all source quotes and disables extraction. Automatic review/expiry filters apply before recall. Facts and raw archive remain separate; explicit facts retain their own intent.

## Schema 6 and derived indexes

Current bundles use schema 6 with 18 business tables including `memory_index_jobs`; rebuildable `memory_embeddings` are omitted. Schema 4/5 restore is explicitly upgraded with strict old/new column checks. Restore requires empty derived indexes, disables memory use/semantic extraction settings, cancels index jobs and preserves the existing quarantine/paused-task policy. Reauthorize desired facts, then `/memory use on`; semantic opt-in is separate. Memory status/revision/hash changes remove derived vectors through migration 6's trigger, including source expiration/erase. Index job hashes/errors do not duplicate fact text. [Semantic reference](semantic-memory.md) owns the indexing/recall details.

Migration 7 adds optional rebuildable `history_embeddings` (source IDs/hashes, generations and vectors, without copied chat text); see the [history reference](../reference/history-retrieval.md). Logical backup is now schema 7 and omits fact/history vectors; restore requires empty derived indexes and disables auto/use/semantic. Source changes, run-history expiry, and settings/floors purge the historical cache.

Migration 8 adds persistent `history_index_jobs`; logical schema 7 includes this table while omitting vectors. Restore cancels historical jobs and fills an empty job table for schema 4/5/6. See the [history reference](../reference/history-retrieval.md) for budgets and leases.

[Current conversational memory additions](memory-assistant.md)：Migration 10, logical backup schema 8, natural settings, short-lived choices and answer diagnostics. Older sections retain their historical scope.
