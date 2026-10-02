# Memory v2 implementation progress

[简体中文](memory-v2-progress.zh-CN.md) · [Documentation](../README.md)

Date: 2026-10-02. Scope: proposal extraction plus durable automatic-memory runtime on `codex/memory-v2`. [Specification](../design/memory-v2.md) remains the complete target. This code has not been deployed to the owner's Telegram bot.

## Proposal extraction

[MemoryExtractor](../../src/kestri/memory_extractor.py) validates immutable source/batch/proposal schemas, owner/scope, opt-in watermarks, fresh/context limits, verbatim Unicode quotes and offsets, supplied target revision, chronology, secrets and temporal bounds. Only fresh direct-owner statements can substantiate facts; inference stays candidate. Reinforcement cannot rewrite content; current state defaults to a 30-day review interval.

The existing DeepSeek/LangChain adapter generates a `MemoryProposal`, using only that structured response tool, no research tools/checkpoints, at most one model request, existing admission/accounting, activity checks, deadline and disabled tracing. Exact quotations establish traceability; they do not prove semantic accuracy or perfect sensitive-data detection.

## Durable runtime

Migration 5 adds owner opt-in/revision/generation/watermarks, ingestion provenance, memory metadata, `memory_jobs`, `memory_sources` and `memory_events`. Default off. `/memory auto on` starts at a new archive watermark; old history is not backfilled. Direct ordinary owner messages enqueue extraction atomically with archive acceptance. Forwarded/external-reply content and explicit task/memory controls do not enqueue facts. A failed foreground answer does not discard an eligible job.

[MemoryRepository](../../src/kestri/memory_repository.py) claims one ordered job per owner after foreground work is idle. Each job supplies one fresh message, at most 12 adjacent context messages / 24000 UTF-8 bytes, and 20 recent eligible memories / 12000 bytes. It uses a 120-second lease and a stable maintenance run across up to 3 attempts, with 5/30-second retry delays. Each attempt captures current versions; publication revalidates proposals and settings/revision/epoch/lease under the owner transaction lock. Facts, source excerpts, events and success commit together. Add/reinforce preserves the head; replace resets head/epoch. Capacity rejection is terminal and visible through `/memory changes`.

[MemoryWorker](../../src/kestri/memory_worker.py) limits extraction to 60 seconds and 2048 output tokens (or lower configured limits). It charges `memory_extract` in the existing micro-USD ledger: default 0.15 USD per job across all attempts, 1.50 USD per UTC month for extraction, also bounded by the owner's total monthly budget. Unknown requests retain reservations. This increment only calls DeepSeek for extraction; CNY embedding conversion is deferred until vector integration.

`/memory pending` shows candidates; `/correct ID full-content` explicitly confirms or corrects one, and `/forget ID` dismisses one. `/memory changes` shows recent automatic events, job states and fixed failure categories. No automatic Telegram change notices are sent. `/memory auto off` cancels queued/in-flight work without removing existing memories. Forget advances a broad old-history cutoff. Backup schema 5 includes the new tables and accepts schema 4 with conservative defaults. Restore disables automatic extraction, cancels jobs and quarantines active/candidate memories. Source retention deletes excerpts and expires dependent automatic facts; erase disables extraction.

## Verification

The extractor has 25 controlled tests. Local complete suite: **191 passed, no skipped cases**, on disposable PostgreSQL 17. Ruff lint/format, mypy (29 modules), all 88 bilingual documents and wheel/sdist build passed; the wheel includes migration 5 and both new runtime modules. Persistent-job tests cover opt-in/provenance/deduplication, foreground priority, concurrent claim, atomic publication, candidate isolation/approval/dismissal, correction/forget races, lease reclamation, bounded retry, accounting, real-framework HTTP mocks, source cleanup and schema 4/5 restore. Run the complete suite against disposable PostgreSQL as described in [run checks](../how-to/run-checks.md). These checks do not establish live extraction quality, Chinese semantic precision or deployed-bot acceptance.

## Remaining increments

Next: pgvector exact-cosine storage and asynchronous indexing, version/hash checks, hybrid recall and lexical fallback, bounded history tools, separate memory-use control, embedding currency accounting, labeled Chinese evaluations and live bot acceptance. Current recall still uses the bounded keyword/recency path (latest 64 eligible records, normally at most 8 injected); it does not yet recall paraphrases semantically. The complete Memory v2 feature is not accepted.
