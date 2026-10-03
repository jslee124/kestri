# Unified assistant controls delivery record

[简体中文](assistant-controls-completion.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-03. Natural language, commands and buttons share conservative routing and existing domain transactions. Task choices bind direct-owner sources, domain, epoch, ten-minute expiry and target revision; clarification chains contain at most three messages. Explicit referenced timing changes need no model. Status, task lists, help and usage use read-only paths; control output uses escaped HTML and navigation buttons.

## Checks

pgvector: 314 passed; ordinary PostgreSQL: 286 passed, 28 vector checks skipped. Ruff, strict mypy for 66 modules, documentation and SQL checks passed; wheel/sdist built. Deterministic routing samples: 25/25; six counterexamples did not route to mutation. This labeled regression is not a measured real-world wrong-operation rate.

Real Telegram used an isolated database/workspace with automatic and semantic memory disabled: natural task query, explicit-zone creation, ambiguous no-change, choice button after restart, selected-only pause, consecutive timing changes, missing time/zone supplementation, details button and mixed-control no-change. Acceptance found and fixed explicit-timezone extraction guidance, duplicated creation notices and model dependence for referenced timing changes. Ordinary task proposals can still fail validation; failure never claims a successful mutation.

## Deployment and recovery

Production never imports synthetic tasks; reconcile the polling cursor before switching back to prevent test replay. Upgrade retains migration 10 and logical backup format 8. Private raw database, logical backup and workspace snapshots are retained; raw backup restored into an isolated target with matching record/checkpoint counts and a readable workspace archive. The old image remains tagged `kestri-app:rollback-before-assistant-controls`. See deployment evidence for actual container and exact-commit remote CI status; synthetic acceptance does not establish longitudinal personalization quality.

[接口](../reference/assistant-controls.md) · [部署证据](evidence/assistant-controls-deployment.json)
