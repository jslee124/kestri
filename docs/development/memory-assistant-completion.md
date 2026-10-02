# Conversational memory delivery

[简体中文](memory-assistant-completion.zh-CN.md) · [Usage reference](../reference/memory-assistant.md)

Updated: 2026-10-02. This scope is implemented; acceptance and deployment are recorded below.

## Implementation

Natural viewing/settings, multiple independent toggles, shared mutation services, bounded home/list/details, owner-only navigation and ambiguity buttons, numbered choices across restart and actual-call memory diagnostics are implemented. Proposals are separate from transactional execution, reusing authority, budgets and idempotence. Ordinary answers remain plain text; controls use escaped HTML and owner-local time. Multiple commands in one message produce split guidance without execution.

Migration 10 adds choice/presentation fields. Logical schema 8 accepts schemas 4–7. Restore clears choices, presentation and diagnostics without replaying writes. Diagnostics store no query/body copies and revalidate current facts and consent before display.

## Verification

All 280 pgvector tests passed; plain PostgreSQL passed 252 with 28 conditional vector skips. Ruff lint/format, mypy on 57 modules, readability of 10 SQL migrations and bilingual documentation links passed; wheel/sdist builds passed. Integration uses real LangChain structured proposals and graph middleware, covering identity, proposal authority, failure receipts, duplicates/restart, target revisions/epochs, forgotten diagnostics and legacy restore.

Isolated database/workspace acceptance used logged-in Chrome and the same Telegram bot, copying only the poll offset: one request enabled auto/semantic, two similar facts were saved naturally, ambiguity made no mutation, a button selected/forgot after restart, remaining facts reached a real answer through hybrid retrieval, evidence showed actual injection, natural use-disable hid old diagnostic bodies, and read-only settings navigation worked. The isolated poller was stopped and offsets coordinated; synthetic memories were never imported into production.

## Deployment and limits

Production advanced from migration 9 to 10, preserving 27 runs/133 messages before startup and the original volumes. A pre-migration raw dump restored in a separate database; checkpoint table counts matched at 10/161/111/251. The owner's independently enabled auto/use/semantic controls stayed enabled. Private schema-8 logical backup and the preserved rollback image remain available. Rollback restores separate volumes instead of reusing upgraded data.

Evidence covers these synthetic workflows and deployment integrity, not every natural expression, longitudinal personalization, all platforms or actual power failure. Conservative lexical routing may require clarification or a command for unsupported expressions. History selection/coverage retain the existing reference limitations.

[Sanitized deployment record](evidence/memory-assistant-deployment.json).

Deployed source: f7580ddaf444223e3cae503281307bb2c9d3235b. Both containers are healthy; production natural home and changes worked after restart. Private snapshots are in .kestri/deployment/2026-10-02-memory-assistant/. Rollback Compose is config-validated; no rollback poller was started.
