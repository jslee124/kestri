# ADR-0007: Automatic and semantic personal memory

[简体中文](0007-automatic-semantic-memory.zh-CN.md) · [Documentation](../README.md)

Date: 2026-10-02. Status: accepted direction; embedding connection and durable opt-in extraction implemented on the feature branch; semantic retrieval and live acceptance pending.

## Context

Explicit-only writes and keyword recall do not meet the desired everyday personal-assistant experience. The owner should not repeat remember commands or exact phrasing. Existing source archives, memory states, transaction receipts and epoch revocation provide useful foundations.

## Decision

Adopt [Memory v2](../design/memory-v2.md): opt-in automatic extraction of owner direct statements, isolated inferred candidates, source-backed consolidation, temporal state, semantic plus lexical recall, and bounded original-history tools. Use Beijing DashScope `text-embedding-v4` at 1024 dimensions, initially through a standalone validated adapter; later store derived vectors with pgvector in the existing PostgreSQL database. Model proposals are validated by the application; memory never authorizes tasks or external effects.

This supersedes the explicit-only/no-vector direction in [ADR-0005](0005-explicit-memory-and-revocable-context.md) **when the corresponding Memory v2 increments are implemented and accepted**. Until then ADR-0005 describes the running product. Keep source/state separation, ephemeral injection, and conservative revocation. Add/reinforce will avoid head resets; replacement/forget/expiry retain epoch invalidation. Initial forgetting uses a broad automatic-history cutoff rather than promising semantic deletion of every paraphrase.

## Alternatives

Adding embeddings alone cannot learn which facts matter. Automatic writes alone cannot recall paraphrases. A separate vector database adds an unnecessary storage boundary for initial personal scale. Putting a downloaded model inside the current 512 MiB app container requires separate resource work; defer local inference behind the adapter contract. Fine-grained semantic tombstones are not a reliable initial anti-resurrection guarantee.

## Consequences and review

Owner opt-in and inspect/correct/forget controls accompany increased personalization. Background jobs, concurrency, budgets, provenance, backup versions and cleanup require implementation before automatic use. Provider inputs leave the machine; local model support is a possible later alternative. Broad history cutoffs sacrifice unrelated old-history recall and must be disclosed in receipts. The standalone smoke is not a memory-quality evaluation or vector-database acceptance. See [connection reference](../reference/embedding.md) and [evidence](../development/embedding-validation.md).

Current implementation boundaries and adjustments are recorded in [progress](../development/memory-v2-progress.md); deployed M0–M4 acceptance remains historical evidence, not automatic-memory acceptance.

Vector storage, durable indexing, use/semantic controls and model-path hybrid recall are now implemented on the feature branch; [runtime contract](../reference/semantic-memory.md) records provisional thresholds, fixed currency conversion and the exact search policy. Historical/live quality acceptance remains pending.
