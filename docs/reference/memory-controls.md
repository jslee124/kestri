# Memory corrections and change notices

[简体中文](memory-controls.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Implemented owner controls and durable automatic notices.

## Direct natural-language controls

[Intent parsing](../../src/kestri/memory/intent.py) accepts complete, anchored Chinese commands, including `把关于Python的记忆改成我现在使用 Rust。`, `忘记关于Python的记忆`, and `更正记忆 Python 改成我现在使用 Rust。`. `/remember`, `/correct ID full-content`, `/forget ID`, and their previous Chinese prefixes remain available. Quoted, hypothetical, embedded, negated and forwarded/external controls cannot authorize writes.

[MemoryService](../../src/kestri/memory/service.py) resolves targets inside the owner transaction. An unquoted full/partial UUID uses the existing unique-ID check only with explicit ID syntax (`/correct`, `/forget`, `更正记忆`, `忘记记忆`). A target in `关于deadbeef的记忆` remains literal content, even if it looks hexadecimal. Other targets use Unicode NFKC, case-folding and whitespace normalization; a literal substring of at least two characters must identify exactly one active/candidate, unexpired owner record across personal/task scopes. Deleted-task records are excluded. The snapshot checks one more than the configured automatic, explicit and candidate capacity; overflow disables automatic resolution.

If a target is absent or ambiguous, no memory/revision/epoch changes. At most five literal or lexical suggestions show IDs, scope and bounded content. Lexical/semantic relevance never authorizes a mutation. The owner chooses with a new `/correct ID full-content` or `/forget ID` command; that command rechecks the current target. There is no implicit “first suggestion” authorization or pending free-form choice. A successful correction creates an explicit replacement, supersedes the old fact and resets context; forgetting also advances the automatic history floor. Existing run-based idempotence and credential rejection apply.

## Automatic change notices

[Publication](../../src/kestri/memory/repository.py) writes a single brief outbox message in the same transaction as a successful extraction job, facts and events. New active facts and replacements include their IDs and up to 120 content characters each, with correction/forget instructions. A job has at most eight operations. Reinforcement, inferred candidates and empty proposals are silent. Network delivery happens later through the existing sender.

The outbox references the extraction maintenance run; existing job/events provide provenance, so no notice table or logical-backup version is added. [Store](../../src/kestri/storage/store.py) checks completed/succeeded status, auto/use consent, settings generation, the resulting epoch and every notified fact's active/time/task eligibility when claiming a notice and immediately before HTTP send. A replacement's expected epoch includes its one committed increment. Revoked notices become `failed` with `MemoryNoticeRevoked` and cleared text; they do not block later queued sends.

The check cannot revoke a Telegram request already in flight. Uncertain sends retain existing conservative recovery behavior rather than blind retries. Restore cancels/quarantines business state and suppresses pending sends; notices are not replayed to advertise restored facts.

## Checkpoint storage

Store connections now pin `search_path=public`. [Migration 9](../../src/kestri/storage/sql/009_checkpoint_schema.sql) moves all four legacy LangGraph tables from `kestri` to `public` without losing rows. PostgreSQL's default `$user` path could previously create them in `kestri` when the role had that name, outside retention's `public` checks. Both copies existing is a `CheckpointSchemaConflict`; the whole migration rolls back rather than mixing state. Back up and inspect that collision before resolving it. Framework tables remain excluded from logical backups and reset on logical restore.

## Verification

[Control integration tests](../../tests/memory/test_memory_controls_integration.py) cover unique correction/forget, ambiguity and explicit selection, similarity without authorization, legacy Chinese IDs, notice restart/reinforcement, disable/forget revocation, replacement epochs and candidate silence. [Schema tests](../../tests/storage/test_checkpoint_schema_integration.py) preserve legacy migration rows and reject collisions without deleting either copy. [Completion evidence](../development/memory-v2-completion.md) separates controlled tests, synthetic quality, actual Telegram checks and deployment.
