# Backup format, restore validation, and retention internals

[简体中文](data-maintenance.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Source: [data.py](../../src/kestri/storage/lifecycle.py), [workspace.py](../../src/kestri/storage/workspace.py), and migration 4. Commands and retention defaults remain in [data lifecycle](../reference/data-lifecycle.md); operational steps are in [backup and restore](../how-to/backup-and-restore.md).

## Operator service and locks

`DataService` receives store, workspace, and `DataSettings`; it has no model/provider client. `status()` counts the 13 backed-up business tables and returns `meta.maintenance`, without exposing record bodies. This count omits business migration and framework tables and does not measure table/file byte sizes or active loop health.

`exclusive()` acquires the transaction advisory lock `kestri-data`, verifies stored owner binding, and for operator work also tries the relevant bot lease to reject a running instance sharing this database. With no identity yet, restore supplies the backup bot ID. It locks conversation rows in ordered chat-ID order before yielding a transaction connection. Automatic cleanup uses `operator=False` but still uses data/conversation locks and busy checks.

These locks coordinate application participants using the same PostgreSQL database. They do not exclude unrelated SQL clients, a poller using another database, or a human modifying workspace files. Backup uses ordinary transaction reads, not a physical PostgreSQL snapshot or explicit repeatable-read/PITR protocol.

`disk_operation()` offloads synchronous file work to a task/thread and awaits it with `asyncio.shield`. If cancellation arrives, it waits for the worker before re-raising, preventing the surrounding lease/rollback scope from ending while that worker still writes. It cannot make thread disk work preemptively cancellable or guarantee recovery from power loss.

## Private file envelope

`encoded()` uses UTF-8 JSON, sorted keys, `ensure_ascii=False`, and `default=str` for database UUID/time values. The outer bundle has exactly `sha256` and `payload`; the SHA-256 covers encoded payload bytes.

```json
{
  "sha256": "SHA-256 of the canonical encoded payload",
  "payload": {
    "format": "kestri-data-v1",
    "kind": "backup",
    "schema": 4,
    "created_at": "2026-10-02T00:00:00+00:00",
    "tables": {"...": ["complete business rows"]},
    "evidence_text": {"run-uuid/evidence-uuid": "retained text"},
    "checkpoints": "excluded-reset-on-restore"
  }
}
```

This is a shape illustration, not a valid restore fixture. Exact tables are `meta`, `conversations`, `runs`, `tasks`, `inbox`, `messages`, `outbox`, `evidence`, `usage`, `events`, `task_changes`, `memories`, `memory_changes`. Columns must match the target schema, including null fields. Business `migrations` and all checkpoint tables are excluded. Credentials are not included as configuration; private business content is still present.

`write_private()` bounds bytes to 64 MiB, requests new parent mode 0700, rejects an immediate symlink parent, exclusively opens the final no-follow file with mode 0600, writes/flushes/fsyncs, and removes a partial file on handled failure. It does not overwrite, encrypt, authenticate the author, tighten all ancestor permissions, or implement atomic rename plus parent-directory fsync.

`read_private()` opens no-follow/nonblocking, checks a regular file, no group/other permission bits, and size at most 64 MiB, then reads at most limit+1. It validates exact envelope keys, checksum, and format. SHA-256 detects corruption, not malicious alteration by someone able to recompute the checksum. Local operator paths are not model capabilities and have different scope from UUID-only research evidence.

## Backup and export creation

`backup()` holds the exclusive operator transaction, streams each table with a named cursor, and counts all rows. It limits total rows to 50000 and accumulated encoded row/text content to 32 MiB before final envelope serialization (which also must fit 64 MiB).

For backup, every `evidence.status='retrieved'` row must have readable retained text. Each read is limited to 64000 characters; a clipped/missing file fails backup instead of silently creating an incomplete attachment set. Attachments use exact canonical run/evidence UUID keys. Export omits attachments and sets `kind='export'`; it is a readable record export, not a restore source.

Default output is `<workspace>/backups/<UUID>.json`; custom operator path is supported. The return is a path printed by CLI. Creating a file on the same volume does not protect against disk loss; custom/external copies have their own permissions/retention. There is no automatic off-device upload or periodic backup job.

## Restore validation stages

`restore(path, apply=False)` reads and validates the private envelope, then checks:

1. Kind `backup`, schema exactly 4, exact business table set, dictionary attachment map, lists of dictionary rows, total row bound.
2. Every supplied row containing `chat_id` matches the configured owner; exactly one identity row has that owner and a positive integer bot ID.
3. Attachment keys exactly match retrieved evidence rows. Keys are two canonical UUID strings; each content is a string of at most 64000 characters.
4. Exclusive data/bot locks; every business target table empty; workspace contains no entries except an optional `backups` directory; `public.checkpoints`, if present, contains no snapshot rows.
5. Set constraints deferred, inspect target `information_schema.columns`, and require each row's column-name set to match exactly.

The explicit checkpoint emptiness check is on `public.checkpoints`; it is not a complete independent audit of orphan blob/write tables. Preview validates these shapes/policies/column sets, but does not insert rows to prove all SQL types, foreign keys, or constraints. Existing schema initialization and workspace creation may already have occurred in CLI setup.

## Restore transformations and apply

Before inserting, restore transforms imported authority and continuity:

| Table / condition | Transformation |
| --- | --- |
| `conversations` | Head null, epoch incremented |
| Active `memories` | `quarantined` |
| Nondeleted `tasks` | `paused`, `restored=true` |
| Queued/running `runs` | `interrupted`, cancellation true, `RestoreQuarantine` |
| Pending/sending `outbox` | `uncertain`, `RestoreQuarantine` |
| Reserved `usage` | `unknown`, amount retained |
| Already inactive/deleted/finished rows | Preserve inactivity/outcome; do not regain authority |

For `--apply`, columns and placeholders use psycopg identifier-safe SQL; JSONB columns are wrapped with `Jsonb`. Deferrable cycles permit insertion order for tasks/runs and memory supersession. Import sets the one-time startup marker, creates evidence through `Workspace.write()`, and repairs serial sequences for `messages.id`, `outbox.sequence`, and `events.sequence` using imported maxima. Graph history is not restored.

Database import and evidence creation occur within the controlled operation, but disk and database have no shared atomic commit. Handled failures roll back database changes and remove newly created evidence/run directories where possible. Cancellation waits for its file worker before rollback cleanup. Abrupt process/power loss can leave orphan files; keep the source and inspect/retry with a fresh target. There is no guaranteed crash-proof resumable restore journal.

The restored bot's first startup discards stale pending Telegram updates and emits a recovery notice. Imported facts need a new explicit save; agreements need explicit resume. This prevents old backup authority from silently overriding later user revocation. See [execution/delivery](execution-and-delivery.md).

## Cleanup selection and database phase

`cleanup(apply=False, before=None, erase=False, operator=True, now=None)` computes archive/evidence/event cutoffs from settings. `before` overrides archive cutoff only; default delete-history sets archive cutoff to current UTC, while evidence/log cutoff still follows their policy unless related run content also expires. A naive archive timestamp is rejected. Erase selects all content cutoffs and additionally revokes memory/tasks.

Under the exclusive transaction, any queued/running run or pending/sending outbox defers cleanup entirely, including erase. Stopping the process does not remove queued database work. A returned `deferred=true` means content was not cleared; inspect persisted work instead of assuming a stopped app implies cleanup success. Preview counts messages, run content, events, and retrieved evidence without requested mutations.

Apply deletes expired archive rows; clears old run requests/results and marks history expired; clears outbox/change acknowledgement text; clears sufficiently old inactive memory/deleted-task bodies; and deletes expired events. Active/quarantined memory and nondeleted agreements retain explicit durable content unless erase. Erase empties all memory content and marks forgotten, empties/deletes task agreements and increments revision, and removes managed backups afterward. Minimal operational identifiers/costs remain.

When messages, run content, evidence, or erase requires invalidation, it clears all conversation heads, increments epochs, and deletes all checkpoint snapshots/blobs/writes while idle. This is intentionally broader than trimming a single historical thread. Saver migration records remain. Evidence is marked expired with `cleanup_pending` before physical removal; old-history source URLs/titles are also cleared.

## File phase, backup pruning, and periodic maintenance

After database commit, cleanup lists pending evidence, removes each UUID-scoped file, and clears its pending metadata after success. A failed unlink leaves expired evidence unavailable and pending for a later successful cleanup. Empty run directories may remain. Database phase and file phase are separate; metadata can revoke use before bytes disappear.

`prune_backups()` considers only non-symlink regular `.json` files with UUID stems directly in workspace `backups`, rejects a symlink backup directory, uses file modification time for age, reads the private envelope, and deletes only `kind='backup'` when old enough or erasing. Exports/custom names/custom paths/external copies are not pruned. Invalid candidate bundles can fail maintenance rather than being deleted blindly.

`maintaining()` runs cleanup immediately and then waits the configured interval. It records latest counts/time or safe exception type in `meta.maintenance`; subsequent attempts can retry pending cleanup. Busy installations can defer indefinitely. There is no complete historical maintenance log or automatic disk-quota enforcement; `/usage`/cost records are not erased to reset allowances.

## Verification and operator limits

[Data lifecycle integration tests](../../tests/storage/test_data_lifecycle_integration.py) cover empty-target validation, corruption/permissions/owner rejection, quarantine, transaction/file failures, sequence behavior, busy deferral, erasure/retention, no-follow cleanup, and cancellation/lease handling. They establish controlled boundaries, not every abrupt crash point or external-copy deletion. A backup-schema change needs an explicit compatibility decision; older bundles are not auto-upgraded by a version-neutral importer.
