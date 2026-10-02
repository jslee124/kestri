# Semantic memory runtime

[简体中文](semantic-memory.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Feature-branch implementation; no production bot upgrade or live private-dialogue evaluation has been performed.

## Controls and data disclosure

`/memory semantic on` enables semantic indexing/recall after the configured embedding connection and vector table are ready. Default off. Active retained facts and bounded queries go to Beijing DashScope; candidate selection goes to DeepSeek. Existing active facts can be indexed, but old raw chat is not extracted. `/memory semantic off` cancels index jobs and restores the original keyword/recency recall; existing local vectors remain reusable. `/memory use off` disables all memory injection and index HTTP calls; automatic extraction is an independent setting controlled by `/memory auto off`. Turning use/semantic on or off resets foreground context/epoch and increments retrieval generation. `/memory` shows all three settings; `/memory changes` shows extraction/index job counts and safe failures. Forwarded controls are rejected.

Automatic extraction still defaults off and only processes direct dialogue after `/memory auto on`. Inferred candidates remain outside context and indexing. `/correct`/`/forget`, review deadlines, source cleanup and erase invalidate derived indexes. A late provider response may still be billed; it cannot publish a revoked fact. Restore disables extraction, use and semantic recall; deliberately reauthorize facts and then `/memory use on` before use, and enable semantic separately if wanted.

## Index contract and workers

Migration [006_semantic_memory.sql](../../src/kestri/sql/006_semantic_memory.sql) always adds settings and `memory_index_jobs`. If the server exposes pgvector, it enables the extension in `public` and creates `memory_embeddings` with `vector(1024)`; the DB role needs extension/table creation permissions. Plain PostgreSQL remains supported and rejects semantic enable with an actionable notice. Use pgvector in the `public` schema for this contract.

A database trigger commits eligible fact changes and index jobs together. Jobs identify memory ID, revision, MD5 content fingerprint, embedding space and retrieval generation; MD5 is change detection, not authentication. Candidate/inactive facts cannot enqueue. Changes invalidate old vectors and cancel stale jobs/runs/reservations. A worker waits for foreground capacity, claims an ordered owner lane, uses a 120-second lease, and preserves a maintenance run across at most three attempts (5/30-second delays). It computes outside transactions and rechecks settings, source state/version/hash, lease and generation before publication. No vector computation can reactivate a source.

The space fingerprints provider, Beijing workspace endpoint, model, 1024 dimensions and `compatible-float-symmetric-l2-v1`. Both facts and queries use the same OpenAI-compatible float recipe, with local L2 normalization before float32 storage/comparison to avoid overflow/underflow. All API vectors/usage remain adapter-validated. This does not pin vendor model weights. A changed space requires an explicit `/memory semantic on` under the new configuration, queues a separate generation and never mixes spaces. No HNSW/IVFFlat index is created: SQL uses exact cosine distance and current-fact joins. [pgvector's official query/index contract](https://github.com/pgvector/pgvector#querying) describes these operators and the exact-search default.

## Retrieval and failure behavior

Each eligible request reads a consistent owner/scoped fact snapshot: active, nonempty, task state, valid time, expiry and review deadline, bounded to the configured automatic plus explicit capacity (at most 1064). Stable communication preferences use a documented content-marker heuristic: at most six / 2000 characters. It is not a perfect preference classifier and needs labeled evaluation.

Queries use the current request followed by up to four recent human/assistant dialogue messages, bounded to 4000 characters and 8192 UTF-8 bytes; original research input is preserved. `nfkc-ascii-overlapping-cjk-bigram-v1` normalizes Unicode, keeps ASCII word terms and overlapping Chinese bigrams with a fixed small stop list. IDF-weighted lexical scores select at most 20 positive matches. SQL retrieves at most 20 exact-cosine candidates, filtering owner/scope, current revision/hash and the exact embedding space. Merge by Reciprocal Rank Fusion, `k=60`.

One structured `MemorySelection` call selects only supplied IDs, at most eight or none; it has no research tools/checkpoint, no retry, at most 512 output tokens and a 12000-byte candidate/query allowance. Foreground query embedding plus selection share a 10-second default deadline and foreground budgets. Provider failure, timeout, invalid selection or unavailable budget returns bounded positive lexical matches; no recent unrelated padding or fabricated dense score. Core preferences and related facts total at most 6000 characters. Main requests still pass final full-input admission.

A retriever caches selected IDs within the run and rechecks eligible facts/versions each model request. Embedding and selector run at most once per run. After additive revision change it selects locally; one final local retry handles a race, then aborts repeated change. Epoch/use changes abort stale work rather than injecting fallback. Memory remains transient model-request data and is not stored in graph messages. In original nonsemantic mode, the previous bounded keyword/recency behavior remains.

## Configuration and accounting

Product configuration uses `DASHSCOPE_API_KEY` plus `KESTRI_EMBEDDING_BASE_URL`, model `text-embedding-v4` and **1024** dimensions. The standalone smoke still supports other provider dimensions. An absent/blank key or absent URL leaves product embedding unavailable; malformed supplied URLs or non-1024 product dimensions fail validation. The URL must be the official Beijing workspace address. Provider keys remain in ignored local configuration.

| Variable | Default | Accepted range / meaning |
| --- | --- | --- |
| `KESTRI_EMBEDDING_CNY_PER_MILLION` | 0.5 | Greater than 0, at most 100; configured CNY input estimate |
| `KESTRI_EMBEDDING_USD_PER_CNY` | 0.15 | Greater than 0, at most 1; fixed operator conversion, not a live FX quote |
| `KESTRI_EMBEDDING_CONVERSION_VERSION` | `fixed-v1` | 1–64 characters; retained in ledger metadata |
| `KESTRI_MEMORY_RETRIEVAL_TIMEOUT_SECONDS` | 10 | Greater than 0, at most 30; combined query embedding/selection deadline |
| `KESTRI_MEMORY_DENSE_MIN_SIMILARITY` | 0.30 | -1–1; provisional recipe-specific filter, **not calibrated quality evidence** |

The configured 0.5 CNY/million estimate matches Beijing online text input in the [official model pricing](https://help.aliyun.com/zh/model-studio/text-embedding-v4) checked on 2026-10-02; it is not a guaranteed future invoice price. Conversion is an explicit local accounting policy. Reserve before HTTP using UTF-8 bytes plus 256 units per text, round USD estimates upward to micro-USD, and retain original CNY estimates/rate/version. Settle validated usage; unknown calls retain conservative reservations. Local secret/size rejection happens before reservation. Free quota does not disable budgets.

`memory_index` shares the default 0.15 USD/job and 1.50 USD/UTC-month maintenance caps with `memory_extract`, and also counts under owner total monthly spending. `memory_query` and `memory_select` count under foreground/background run and owner monthly caps. No CNY amount is added directly to the USD ledger. Original-currency metadata is not a provider bill. Probe smoke remains outside the database ledger.

## Deployment and compatibility

The base Compose image/volume remain unchanged. Build the optional same-base PostgreSQL 17 Alpine extension image with checksummed pgvector 0.8.7 source:

```bash
docker compose -f compose.yaml -f compose.vector.yaml build postgres
```

For an existing installation, stop the app and make a private logical backup with the current code/config first. Recreate PostgreSQL using the override, then rebuild/start the app with both Compose files. Keep the existing database/workspace volumes; do not delete them. This is operator deployment, not an action already performed by this implementation. See [operations](../how-to/operate-local-agent.md) and [backup/restore](../how-to/backup-and-restore.md). Confirm healthy schema setup before `/memory semantic on`. The override preserves the original database major/distribution/data directory; packaging and disposable DB checks do not prove an owner's volume upgrade or installed-bot acceptance.

Backup schema 6 includes settings and index jobs but omits rebuildable vector rows. Restore accepts schema 4/5/6 with strict column checks and conservative defaults, requires empty derived indexes, quarantines active/candidate facts, cancels index jobs and disables all memory controls. Cleanup/erase removes source-derived vectors through the same status-change trigger; explicitly retained facts can persist under their separate retention intent. Index jobs keep IDs/hashes and safe errors, not copied fact text.

## Verification boundary

[Unit tests](../../tests/test_semantic_memory.py) cover lexical/fusion/query/space contracts. [Database tests](../../tests/test_semantic_memory_integration.py) cover enqueue/versioning, restart lease recovery, cancellation, in-flight disable/forget, shared budgets, CNY metadata/unknown usage, paraphrase selection over HTTP mocks, lexical fallback/no-match, graph injection, source cleanup and schema 5/6 recovery. CI uses separate plain PostgreSQL and pgvector legs; vector tests skip only in the plain leg. Source/wheel checks must include migration 6 and the three new modules.

These prove policy/data boundaries and controlled orchestration, not semantic accuracy of actual provider output. The labeled Chinese corpus, historical tools, live Telegram/provider tests and long-term recall evaluation remain separate increments.
