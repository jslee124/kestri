# Memory v2 implementation progress

[简体中文](memory-v2-progress.zh-CN.md) · [Documentation](../README.md)

Current status (2026-10-02): the [completion record](../development/memory-v2-completion.md) supersedes earlier pending/deferred statements below. Natural controls, change notices, extraction/selection/history-answer synthetic evaluation and history calibration are implemented. Independent human and longitudinal quality are unmeasured.

Date: 2026-10-02. Scope: proposal extraction, durable runtime, semantic fact recall, and bounded lexical history tools on `codex/memory-v2`. [Specification](../design/memory-v2.md) remains the complete target. The verified revision is now deployed to the owner’s Telegram bot; auto/semantic remain off. See the [deployment record](../how-to/deploy-memory-v2.md).

## Proposal extraction

[MemoryExtractor](../../src/kestri/memory/extractor.py) validates immutable source/batch/proposal schemas, owner/scope, opt-in watermarks, fresh/context limits, verbatim Unicode quotes and offsets, supplied target revision, chronology, secrets and temporal bounds. Only fresh direct-owner statements can substantiate facts; inference stays candidate. Reinforcement cannot rewrite content; current state defaults to a 30-day review interval.

The existing DeepSeek/LangChain adapter generates a `MemoryProposal`, using only that structured response tool, no research tools/checkpoints, at most one model request, existing admission/accounting, activity checks, deadline and disabled tracing. Exact quotations establish traceability; they do not prove semantic accuracy or perfect sensitive-data detection.

## Durable runtime

Migration 5 adds owner opt-in/revision/generation/watermarks, ingestion provenance, memory metadata, `memory_jobs`, `memory_sources` and `memory_events`. Default off. `/memory auto on` starts at a new archive watermark; old history is not backfilled. Direct ordinary owner messages enqueue extraction atomically with archive acceptance. Forwarded/external-reply content and explicit task/memory controls do not enqueue facts. A failed foreground answer does not discard an eligible job.

[MemoryRepository](../../src/kestri/memory/repository.py) claims one ordered job per owner after foreground work is idle. Each job supplies one fresh message, at most 12 adjacent context messages / 24000 UTF-8 bytes, and 20 recent eligible memories / 12000 bytes. It uses a 120-second lease and a stable maintenance run across up to 3 attempts, with 5/30-second retry delays. Each attempt captures current versions; publication revalidates proposals and settings/revision/epoch/lease under the owner transaction lock. Facts, source excerpts, events and success commit together. Add/reinforce preserves the head; replace resets head/epoch. Capacity rejection is terminal and visible through `/memory changes`.

[MemoryWorker](../../src/kestri/memory/worker.py) limits extraction to 60 seconds and 2048 output tokens (or lower configured limits). It charges `memory_extract` in the existing micro-USD ledger: default 0.15 USD per job across all attempts, 1.50 USD per UTC month for extraction, also bounded by the owner's total monthly budget. Unknown requests retain reservations. This increment only calls DeepSeek for extraction; CNY embedding conversion is deferred until vector integration.

`/memory pending` shows candidates; `/correct ID full-content` explicitly confirms or corrects one, and `/forget ID` dismisses one. `/memory changes` shows recent automatic events, job states and fixed failure categories. No automatic Telegram change notices are sent. `/memory auto off` cancels queued/in-flight work without removing existing memories. Forget advances a broad old-history cutoff. Backup schema 5 includes the new tables and accepts schema 4 with conservative defaults. Restore disables automatic extraction, cancels jobs and quarantines active/candidate memories. Source retention deletes excerpts and expires dependent automatic facts; erase disables extraction.

## Verification

The extractor has 25 controlled tests. Local complete suite: **191 passed, no skipped cases**, on disposable PostgreSQL 17. Ruff lint/format, mypy (29 modules), all 88 bilingual documents and wheel/sdist build passed; the wheel includes migration 5 and both new runtime modules. Persistent-job tests cover opt-in/provenance/deduplication, foreground priority, concurrent claim, atomic publication, candidate isolation/approval/dismissal, correction/forget races, lease reclamation, bounded retry, accounting, real-framework HTTP mocks, source cleanup and schema 4/5 restore. Run the complete suite against disposable PostgreSQL as described in [run checks](../how-to/run-checks.md). These checks do not establish live extraction quality, Chinese semantic precision or deployed-bot acceptance.

## Semantic storage and recall

Migration 6, atomic index triggers/jobs, exact pgvector cosine storage, versioned symmetric L2 encoding, CNY-to-USD reservations, owner use/semantic controls and hybrid recall are implemented. [Semantic runtime reference](../reference/semantic-memory.md) is the current numeric/behavior contract. The base Compose/production volumes remain unchanged; an optional same-base PostgreSQL 17 Alpine + pgvector 0.8.7 override was built and tested in an isolated container. Existing embedding key/URL are read locally, never embedded in source.

Controlled verification: **208 passed, no skipped cases** with that pgvector image; **195 passed, 13 vector cases skipped** with ordinary PostgreSQL 17. Semantic tests include actual framework selection/research requests over HTTP mocks and absence of selected memory in saved graph messages. Ruff lint/format, mypy (32 modules), bilingual documentation and wheel/sdist checks cover the new increment. The previous 191-case count above describes the preceding extraction increment. None of these results constitutes a live private-dialogue provider test, Chinese recall-quality gate, existing-volume upgrade or deployed-bot acceptance.

## Bounded history tools

[HistoryRetriever](../../src/kestri/history/retriever.py) is registered in the foreground graph only with both auto/use enabled; auto changes reset head/epoch. Application dependencies fix owner/task scope. Search covers the newest at most 200 eligible turns and five positive-match snippets; same-run handle reads recheck consent and complete source hashes. Turns have at most 12 messages/8000 characters, oversized turns are skipped whole, and zero matches are never padded. No new tables/migration are added; historical vector indexing is not implemented. See the [contract](../reference/history-retrieval.md).

The history increment has nine controlled tests including actual-framework HTTP mocks, task scoping, and the 200-turn window. Full local pgvector suite: **217 passed**; ordinary PostgreSQL: **204 passed, 13 vector tests skipped**. Ruff, mypy (33 modules), 92 documents, and packaging checks pass. The preceding 208 count describes the previous semantic-fact increment. No private-dialogue provider calls or deployment acceptance were performed; full Memory v2 still awaits evaluation.

## Domain packages and historical semantic cache

Source and tests now follow agent/memory/history/tasks/storage/integrations, with entry/configuration/application composition at the root. The [layout guide](repository-layout.md) and source links are synchronized. The directory commit is separate from behavior changes and preserves existing SQL object names.

Migration 7 adds revocable derived history vectors with a separate complete-message JSON encoding space. A run indexes at most nine turns on its first search, with at most three distinct query embedding attempts and successful-query caching. Exact cosine and lexical candidates fuse using RRF; output reports eligible/indexed counts without claiming complete archive coverage. Source changes, run-history expiry, and settings/floor changes purge caches; reads and publication revalidate hashes. Logical backup remains schema 6 and omits both vector tables; restore disables all memory switches. See the [history reference](../reference/history-retrieval.md).

Six controlled semantic history tests cover dense-only candidates, fixed-category fallback, usage, in-flight revocation, coverage bounds, main-graph search/read, and backup/restore. Local pgvector: **223 passed**; ordinary PostgreSQL: **204 passed, 19 vector cases skipped**. Ruff, mypy (40 source modules), 94 bilingual docs, and wheel/sdist checks pass. No deployment or actual private-dialogue provider request occurred; these checks do not establish Chinese quality gates.

## Background history indexing

Migration 8, `HistoryIndexWorker`, valid-lease billing, foreground priority and transactional publication are implemented. Background registration covers all eligible post-floor sources beyond the nine query-time additions; append/edit increments the source revision and blocks old in-flight publication. The shared maintenance monthly cap includes historical indexing, and foreground caches avoid repeated charges. Schema 7 includes jobs, strictly accepts 4/5/6, and disables/cancels imported work. The [history reference](../reference/history-retrieval.md) defines the current contract.

Nine job cases: local pgvector **232 passed**; ordinary PostgreSQL **204 passed, 28 vector cases skipped**. Ruff, mypy (41 source modules), 94 documents and wheel/sdist checks pass. The preceding 223 count describes the previous increment. No deployment or actual private-service request occurred; Chinese quality evaluation and isolated live acceptance remain pending.

## Candidate evaluation and readable SQL

Eight migrations now use expanded definitions/conditions, descriptive trigger row variables, and consistent indentation. A CI readability guard checks indentation and line width. Token comparison confirms unchanged SQL behavior except local variable names; disposable PostgreSQL tests check execution. [Chinese evaluation](memory-evaluation.md) adds 120 synthetic labeled cases, reproducible scoring and live text-embedding-v4 evidence. Development-only calibration raises the fact threshold to 0.50; the history JSON recipe has a separate provisional 0.30 threshold. This measures candidates, not extraction, final selection or injection quality. Local pgvector: **241 passed**; ordinary PostgreSQL: **213 passed, 28 skipped**. Ruff (73 Python files), mypy (42 modules including the evaluation runner), 98 bilingual documents, SQL guard and wheel/sdist passed. [Isolated live validation](memory-live-validation.md) covers actual automatic extraction, semantic recall, history search/read, process restart, forget and restore quarantine. Source-reference failures are retained; exact anchor hints, safe diagnostics and bounded annotation retries were added. The original bot was restored to its previous runtime.

## Persistent deployment

Revision `b1d7bf2` now runs in the existing bot with migration 8 and pgvector 0.8.7. Original volumes/data were retained; a full pre-upgrade dump was restored in a disposable database, and the workspace archive was read-checked. Both containers are healthy; actual Telegram controls responded before/after restart. Auto/semantic remain off. The prior paragraph records the earlier isolated acceptance; this later deployment supersedes its old-runtime status. See the [deployment record and rollback procedure](../how-to/deploy-memory-v2.md).

## Final implementation

Current final collectors and acceptance are recorded in the [completion record](memory-v2-completion.md). Natural-language ambiguity controls and proactive notices are implemented. Independent human/domain review and longitudinal accuracy remain unmeasured.
