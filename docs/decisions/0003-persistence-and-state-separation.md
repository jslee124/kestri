# ADR-0003: Use PostgreSQL and separate conversation, memory, task, and execution state

[简体中文](0003-persistence-and-state-separation.zh-CN.md) · [Documentation](../README.md)

- Status: Accepted
- Decision date: 2026-09-30
- Updated: 2026-10-01
- Implementation: M1 messages, checkpoints, runs, delivery, usage, and evidence implemented; task/memory schemas and retention deferred

## Context

One Telegram chat must support conversation, recurring work, and personal memory without becoming one ever-growing model request. Restarts, context compression, correction, forgetting, and delivery recovery need different durable records.

The project is a single-owner local application, but long-term personal use requires persistence beyond in-memory demonstrations. Storage should be understandable and support established framework adapters.

## Decision

Use one local PostgreSQL instance for durable application records and LangGraph persistence. Store full research material and generated files in the dedicated workspace, with references and provenance in the database.

Maintain separate logical categories: original message archive, graph checkpoints, personal memory, task agreements, runs/delivery, and evidence metadata. Separation is semantic; M1 schemas and adapters exist for research; task/memory lifecycle schemas remain open.

Use a main conversation thread and independent contexts for background executions. Retrieve relevant task evidence through message associations instead of merging entire background histories.

LangGraph provides thread-scoped checkpointers and cross-thread stores. PostgreSQL adapters exist for both. See the [persistence guide](https://docs.langchain.com/oss/python/langgraph/persistence), [checkpoint reference](https://reference.langchain.com/python/langgraph/checkpoints), and [PostgresStore reference](https://reference.langchain.com/python/langgraph.store.postgres/base/PostgresStore). Business task state and the original archive remain Kestri's responsibility.

Personal memory initially uses structured and keyword retrieval. No separate vector database or embedding service is selected. Remembering is explicit; inferred preferences require acceptance. Compression and memory writes are separate operations.

## Alternatives considered

| Alternative | Tradeoff |
| --- | --- |
| In-memory state | Simple for experiments but loses durable state on restart |
| SQLite | Reasonable for a small local application; PostgreSQL is selected for existing checkpoint/store adapters and the accepted persistence-learning goal |
| Checkpoints as the only history | Compression and pruning can remove original messages; execution state does not define task authorization or memory lifecycle |
| One permanent thread for everything | Background traces increase context and make task/evidence association harder |
| Vector-first memory | Adds embedding, retrieval, and deletion complexity before semantic retrieval has demonstrated value |
| Multiple specialized databases | Adds operational and consistency boundaries without a current first-version need |

## Consequences

PostgreSQL adds a local service, backup work, and migration responsibility. Choosing it does not by itself make the product production-ready or guarantee correct concurrency.

Separate records make task control, provenance, correction, and recovery easier to reason about, but require consistent identifiers and deliberate lifecycle coordination. Delivery cannot be made exactly-once merely by using a database transaction around an external Telegram call.

Forgetting and retention must account for copies in summaries, checkpoints, artifacts, and backups. Current execution state must remain usable when obsolete history is pruned. A restore must reconcile deleted tasks and forgotten memories before resuming work.

Detailed lifecycle rules are in [security and data](../design/security-and-data.md); operational defaults and flows are in [architecture](../design/architecture.md). Acceptance criteria are in [requirements](../design/requirements.md).

## Review conditions

Reconsider storage if installation burden, measured concurrency, scale, or offline requirements conflict with the chosen deployment. Add semantic retrieval only when actual memory usage reveals a limitation. Review archive/retention and deletion semantics before changing storage or restoring old data.
