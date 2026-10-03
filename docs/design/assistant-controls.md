# Unified assistant controls

[简体中文](assistant-controls.zh-CN.md) · [Documentation](../README.md)

2026-10-02: approved for implementation. Natural language, commands and buttons share services without arbitrary command/configuration execution.

## Interaction

One entry routes tasks, memory and runtime controls. Support task listing/pause, current activity, stop-current, new topic, help and usage queries. Read-only queries take deterministic paths without model calls. Quotes, negation, hypothetical and forwarded content cannot authorize writes; incompatible mixed controls request separate instructions.

Ambiguous tasks show at most five numbered choices/buttons. Missing timing can be supplied as an explicit fragment; ordinary conversation is not a control supplement. Bind original owner messages, action, target revision, epoch and ten-minute expiry; survive restart, revalidate before commit, and consume success. Settings reset, new topic, cleanup and restore revoke choices.

## Presentation and implementation

Shared routing delegates policy/transactions to domain services. Task summaries paginate, with local-time details; status, usage, help and failures use escaped HTML and read-only navigation. Mutation buttons only select an issued short-lived operation; navigation never toggles settings or deletes tasks directly.

Reuse the durable choice field with a task/memory domain discriminator. Logical restore clears choices rather than restoring authority. Preserve original requests; supplements use a bounded chain of the same owner's direct messages. Proposals cannot manufacture sources.

## Acceptance

Cover colloquial requests, references, negation, mixed controls, stale/expired choices, repeat clicks, timing revisions and restart. Report routing, wrong mutations and clarification completion separately; simulated proposals do not prove live language understanding. Check both databases, lint/types/SQL/docs/packages; isolated synthetic Telegram acceptance precedes snapshots, deployment/restart, push and exact-commit CI. Longitudinal personalization remains separate.

Implementation and acceptance: [delivery record](../development/assistant-controls-completion.md).
