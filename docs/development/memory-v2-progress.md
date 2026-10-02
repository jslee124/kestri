# Memory v2 implementation progress

[简体中文](memory-v2-progress.zh-CN.md) · [Documentation](../README.md)

Date: 2026-10-02. Scope: first implementation increment on `codex/memory-v2`. [Specification](../design/memory-v2.md) remains the target; this is not whole-feature acceptance.

## Implemented proposal extraction

[MemoryExtractor](../../src/kestri/memory_extractor.py) implements strict immutable Pydantic source/batch/existing-memory/proposal schemas. Owner, activation and forgetting cutoffs, fresh/context count, byte admission, task scope, and source eligibility are validated before model invocation. Configured secrets and recognizable credential markers are rejected before sending text. An opt-in batch is a trusted repository snapshot, not a model-created authorization token.

It uses the existing DeepSeek/LangChain path with only a structured `MemoryProposal` response tool, no research/execution tools, no checkpoint saver, at most one model call, existing complete input/output admission and fee reservations/settlement, outer timeout, disabled tracing, and activity checks before/after invocation. The caller must supply a live Budget tied to an authorized run; a future maintenance worker must register its own run and recheck settings/revisions inside a commit transaction.

Application policy checks verbatim Unicode source offsets, fresh direct-owner attribution, inferred-candidate isolation, supplied target/revision/category/scope, source chronology, duplicate operations, secret content and timezone-aware date bounds. Reinforcement cannot rewrite target content; current-state facts without explicit expiry/review receive a 30-day review interval from source time. Empty proposals are valid. Return `ValidatedExtraction` containing the captured batch and normalized operations. Validation never performs SQL writes, updates a cursor, sends a notice or enables runtime memory automatically.

## Verification

25 extractor tests passed, including a real framework invocation over HTTP mock transport: exactly one provider request, only the proposal tool, one reservation/settlement, and validated output. Other tests cover invalid references, inferred writes, forwarded/external sources, history cutoffs, owner/scope, stale replacement, changed reinforcement, secrets, naive dates and duplicate/invalid proposals. Full local suite: 106 passed, 66 database-dependent tests skipped. Ruff lint/format, mypy (27 source modules), documentation links/translations and `git diff --check` passed. Tests do not establish semantic precision on actual model outputs or live provider extraction quality.

## Remaining increments

No migration, persistent maintenance run/jobs, opt-in UI, candidate approval, automatic publication, source capture at ingestion, pgvector storage, hybrid retrieval, history tools, currency conversion, or lifecycle/backup integration is implemented yet. The running Telegram bot continues explicit memory behavior. Complete these in the order specified, with disposable-database, concurrency, evaluation and separate live acceptance evidence. Sensitive/hypothetical content interpretation still depends on model behavior and the future policy classifier; exact-source validation alone is not semantic proof.
