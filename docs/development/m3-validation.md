# M3 validation record

[简体中文](m3-validation.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Status: M3 verified for explicit personal memory and managed conversation context. Retention enforcement, physical deletion, backup/restore, and integrated personal-use acceptance remain M4 work.

## Revision and environment

Work branch: `codex/m3-memory-context`, based on `bf16a00`. Local environment: macOS, Python 3.14.7, uv 0.12.3, OrbStack Docker/Linux arm64, and PostgreSQL 17. Dependencies remain unchanged: LangChain 1.4.3 and LangGraph 1.2.12 from the lockfile. The live Telegram memory/restart checks ran application image `sha256:b837d266c6c915939da546715635d940bf53537933e97d53929d2ae23ed2fc38`. Final source also settles observed summary usage before rejecting an invalid summary; its verification is recorded below. Final deployment successfully started image `sha256:e9e2d2d00ed3032b8b7459ccce443a41fa040357ffe89c1c320d926a0850b822` with migrations 1–3 and no active validation memories, tasks, or runs. Telegram API readback confirmed all 14 commands for default/Chinese menus. Remote CI and publication are recorded separately when available.

## Controlled checks

110 tests pass against an isolated disposable PostgreSQL database, with no skips. Ruff lint/format and strict mypy pass. Real LangChain middleware, agent message serialization, and PostgreSQL checkpointing are exercised with mocked external responses; these checks do not call the provider.

Memory checks cover exact explicit content, source/scope/time/status, concurrent and duplicate application, restart after commit before acknowledgement, correction/supersession, forgetting, scope/expiry, ambiguous targets, unauthorized/forwarded instructions, quoted explanations, inferred suggestions, and recognizable credentials. Retrieved memory is ephemeral in the model request and absent from saved graph messages. Forgetting invalidates the foreground head, old result association, and old evidence access; stale background work cannot begin new billable actions, and stale foreground/background completion sends a safe notice instead of the old answer and cannot restore the foreground head.

Forced compression retains a current “Python replaces TypeScript” correction, source references, and the recent complete tool-call/result pair. Original dialogue content remains unchanged in canonical records and can be inspected through `/history RECORD_ID`. The checkpoint contains a historical-data summary instead of the old prefix. A fixture summary containing quoted `/remember` and `/task` instructions creates no memory or task; authorization remains in application records and control routing. Separate checks bound oversized input and invalid output. Existing spending, cancellation, timeout, tool boundary, task, scheduling, and delivery tests remain passing.

These are tested transitions and adversarial fixtures, not proof of immunity to every model injection, arbitrary crash point, or network outage. Summary quality remains model-dependent.

## Real DeepSeek compression

A separate isolated database fixture seeded a long synthetic conversation and canonical original messages. It included an earlier TypeScript choice, its explicit replacement by Python, quoted source instructions, padding to force compression, and a recent complete tool interaction. The actual DeepSeek official API generated the summary and the subsequent answer with no SDK retries; no Telegram delivery or web retrieval was needed for this fixture.

Exactly one compression event was recorded. The final answer selected Python and explicitly said it replaced TypeScript. No personal memory or task was created. The two provider requests produced a local estimated charge of $0.001876. [Sanitized provider evidence](evidence/m3-live-model.json) retains the synthetic answer/summary, compression metadata, usage, and result status. This artificial trigger verifies real integration, not a long-running personal-use trial or broad summary-quality benchmark.

## Real Telegram memory and restart

The owner chat explicitly saved a temporary global demo color as blue. A normal question was answered using blue. An explicit ID-based correction saved green and superseded blue. The app was restarted; a new question used the current green memory. An explicit forget command tombstoned the corrected entry. After another restart, a question requesting only current valid memory was answered with “I do not know; no valid memory is available.” `/memory` then showed an empty active list.

Database inspection confirmed the blue row is `superseded`, green is `forgotten`, zero active memories, zero non-deleted tasks, and zero queued/running runs. The six validation runs completed and their saved notifications/results were delivered. The three memory controls made no model calls; the three questions made real DeepSeek calls without web retrieval. The local estimated charge was $0.000813. Combined with the separate compression fixture, the observed estimate is $0.002689; these configured estimates are not provider invoices.

[Sanitized Telegram metadata](evidence/m3-live-telegram.json) preserves IDs, supersession, statuses, timestamps, usage totals, and delivery attempts without credentials, owner/chat IDs, full messages, reasoning, or source text. Temporary validation memories were removed from active use, not physically erased. No new recurring task was created. Task-scoped retrieval and stale background revocation were verified in controlled checks rather than a live scheduled memory briefing.

## Persistence and deployment

Additive schema migration 3 is idempotent and preserves existing M1/M2 records. Memory changes and their run-keyed acknowledgement ledger commit atomically. Memories, canonical messages, task agreements, run state, and checkpoints remain independent. The wheel includes all three SQL migrations.

Compose retains the existing non-root/read-only app, bounded resources, dedicated workspace/database volumes, no Docker socket/home mount, and no published database port. Ordinary restart preserved current memory; correction/forget epochs prevented reuse of old context after restart. Container observations cover Linux arm64 on this macOS host; they do not establish VM isolation, arbitrary-code safety, or other platforms.

## Requirement and case coverage

M3 covers MEM-001 through MEM-003, CTX-002, memory portions of CTX-001/SEC-002/DATA-001/OPS-001, and active-memory portions of DATA-002. AC-08 is verified by the controlled explicit-write/inference/source/forget checks and live save/correct/restart/forget observations. AC-09 is verified by combining M1/M2 reply/background evidence with forced-compression, original-history, and real-provider correction preservation above.

AC-10 gains memory/summary attack and revocable-context coverage. AC-11 gains expiry and removal from active memory use; archive retention, physical deletion, and restore reconciliation remain pending. AC-12 gains summary admission, output, call, time, and shared spending bounds through existing controls. Full first-version acceptance remains M4; earlier M0/M1/M2 records retain their historical evidence boundaries.

## Limits and next increment

Only explicit memory controls write facts; no autonomous extraction, vector index, pending-suggestion workflow, or semantic correction target is implemented. Every successful memory change resets foreground context and excludes older epoch replies/evidence from automatic use, trading continuity for revocation. Historical rows, messages, and checkpoints remain readable through explicit archive inspection; `/forget` does not erase them or external provider copies. `/new` preserves memory and tasks.

Compression uses the locked LangChain middleware with tested protected-method overrides. Review the extension when upgrading dependencies. Full summary input must fit; no silent clipping, fabricated fallback, or unlimited retry is provided. M4 must implement lifecycle/restore reconciliation, operational documentation, and an integrated personal-use trial before claiming the complete first version.
