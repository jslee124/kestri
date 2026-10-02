# ADR-0006: Conservative local data recovery

[简体中文](0006-conservative-data-recovery.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02.

Status: accepted and implemented in M4.

## Context

DATA-002 and AC-11 require that restoring an old backup cannot silently revive a later-forgotten fact or deleted task. A snapshot alone cannot know revocations that happened after it. A separate revocation journal would add storage consistency, backup ordering, migration, and failure modes to a small single-owner product.

## Decision

Use bounded private logical snapshots of business records and evidence. Exclude model checkpoint/reasoning state and credentials. Restore only into an empty, same-owner target. Quarantine every imported active memory and pause every imported nondeleted task. Require new explicit owner authorization for retrieval/scheduling. Reset context and quarantine unfinished executions/deliveries/usage reservations. At first recovered Telegram startup, discard pending commands and announce the boundary before accepting new requests.

Apply category retention and physical evidence unlink while idle, with content redaction and graph-state invalidation. Retain minimal deduplication, revocation, identity, and financial markers. Keep backup expiration distinct from active-data deletion. Details live in the [data reference](../reference/data-lifecycle.md).

## Alternatives and consequences

Direct snapshot replay is simpler but unsafe for later revocations. An independent append-only revocation journal could preserve selected active state but requires another trustworthy durable authority and reconciliation protocol. Full PostgreSQL dumps preserve execution internals and need a separate safe migration/revocation procedure. Defer these until their complexity is justified.

The selected design sacrifices continuity: legitimate old memory must be re-entered and legitimate tasks resumed explicitly. Pending messages at the recovered startup boundary are discarded. Backups are unencrypted private local data, not authenticated against malicious authors. They have size/schema bounds and need owner-managed off-device copies. Controlled failures roll back; abrupt loss during file work can leave orphan evidence. These limits are documented rather than presented as universal recovery guarantees.

## Review conditions

Revisit for multi-user/cloud deployment, large datasets, independent code sandboxes, encrypted or remote backup storage, selective continuous recovery, schema upgrades, or a durable external revocation journal. Do not add automatic permission restoration based on model summaries or old snapshots.
