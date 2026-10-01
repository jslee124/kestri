# ADR-0005: Explicit memory and revocable conversation context

[简体中文](0005-explicit-memory-and-revocable-context.zh-CN.md) · [Documentation](../README.md)

Date: 2026-10-01. Status: accepted for M3.

## Context

Personal memory must survive restart without becoming an authorization channel. Forgetting must also remove cached influence from graph state and summaries, while originals remain independently inspectable. Kestri already separates owner controls, PostgreSQL business records, research tools, and LangGraph checkpoints.

## Decision

Use deterministic, explicit owner memory commands and PostgreSQL rows with scope, provenance, status, supersession, expiry, and run-keyed acknowledgements. Do not extract memories from archives or model inference. Begin with structured/keyword retrieval, bounded entry counts, and ephemeral injection into model requests. Research and summarization expose no memory-write or task-management capabilities.

Increment an owner context epoch and reset the committed foreground head on memory changes or expiry. Exclude earlier-epoch results/evidence from automatic context; check epochs before new billable work and foreground head commits. Preserve tombstones and history for explicit inspection. This broad invalidation is deliberately simpler than trying to remove every semantic paraphrase from all old summaries.

Use the locked LangChain summarization middleware's safe-cutoff behavior. Extend its summary request to retain Kestri cost admission, cancellation, input/output caps and bounded attempts. Keep original messages in their existing archive. Summaries are untrusted historical data; permissions, task agreements, and memory remain outside them.

## Alternatives

Vector storage and automatic inference add retrieval/consent complexity before demonstrated need. Model-authored memory tools enlarge the source-injection boundary. Surgical summary scrubbing risks missing paraphrases; regenerating from full retained history risks re-extracting forgotten facts. Retaining an unbounded main transcript makes request cost and admission unpredictable. These approaches are deferred.

## Consequences and review

Memory changes reset current conversation continuity; old automatic replies may become unavailable. Explicit `/history` remains accessible without model injection. Forgetting is active-use exclusion, not physical erasure of all local/external copies. In-flight external calls cannot be recalled. Backup restore must reconcile tombstones before retrieval and remains M4.

Summary quality depends on the model. If safe compression cannot fit the budget, stop and offer fresh context. The protected summary-method extension is tied to the lockfile and regression tests; revisit on framework upgrades. Revisit epoch granularity only with evidence that a narrower invalidation reliably prevents resurrection.

Primary source checked 2026-10-01: [LangChain summarization middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#summarization). Application-level consent, epochs, and deletion boundaries are Kestri decisions.
