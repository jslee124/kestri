# Runnable milestones

[简体中文](milestones.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Status: accepted delivery sequence; M0 verified; M1 not started.

## Purpose and current position

Deliver Kestri through small, runnable increments. Each milestone defines an observable result and the evidence needed to call it complete. This document is an engineering delivery record, not an installation tutorial or a detailed implementation schedule.

[Product](../design/product.md) defines scope, [requirements](../design/requirements.md) defines acceptance, and [architecture](../design/architecture.md) and [security and data](../design/security-and-data.md) define intended mechanisms and defaults. This document orders delivery without replacing those sources.

**Current next target: M1.** M0 is implemented and verified as a developer CLI; see the [validation record](m0-validation.md). M1 is the first complete Telegram product workflow. Later milestones build on earlier ones and preserve their accepted behavior.

| Milestone | Runnable outcome | Status | Evidence |
| --- | --- | --- | --- |
| M0 | Local agent with a real DeepSeek model/tool interaction | Verified | [M0 record](m0-validation.md) |
| M1 | Telegram research with sources and follow-up | Not started | None |
| M2 | Recurring briefing and task management | Not started | None |
| M3 | Personal memory and managed conversation context | Not started | None |
| M4 | Deployable first version accepted for personal use | Not started | None |

## Rules for completion

- Safety, resource limits, and necessary persistence/recovery accompany the capability that introduces their risks. M4 consolidates evidence rather than postponing those controls.
- Connect each milestone to stable requirement and acceptance IDs. A reference can cover only part of a case during an early milestone; record that scope explicitly. The full case stays unverified until all its outcomes have evidence.
- Distinguish controlled/offline checks from real provider, Telegram, recovery, and deployment observations. Mock success does not establish live integration.
- Do not label a milestone verified merely because code exists or one happy-path demo succeeds. Meet its exit criteria, preserve evidence, and record known limitations.
- Resolve open choices that affect the next milestone before calling it complete. Exact APIs, schemas, package versions, and task breakdowns are not prescribed here.

## M0: Validate the model integration

### Outcome and scope

Run a minimal local LangChain agent against the DeepSeek official API. Give it one deterministic, controlled test tool and inspect a genuine model-request/tool-result/answer cycle. This establishes integration behavior before Telegram and web retrieval add more moving parts.

### Exit criteria

- The real model requests the tool, consumes its result, and produces a relevant answer.
- Multi-turn interaction retains the required provider state. Validate the selected thinking mode and record the model identifier and dependency versions used.
- A tool failure, a provider failure, and a configured call/time limit produce bounded, understandable outcomes.
- Load credentials through local configuration; keep secrets out of prompts, output, and logs. The test tool has no arbitrary host access.
- Preserve invocation metadata and available usage data without claiming precise billing that was not observed.

### Traceability and evidence

Foundations for CHAT-001, SEC-001, OPS-001, and OPS-002; model/tool portions of AC-12. Retain redacted live interaction evidence and controlled failure checks. This does not verify the full application policy or AC-12.

## M1: Deliver immediate research in Telegram

### Outcome and scope

The configured owner sends a question in a private Telegram chat, receives a concise synthesis with source links, and replies to continue discussing the evidence. Integrate controlled search/extraction, scoped workspace material, and PostgreSQL-backed conversation/run records. Provide basic status, cancellation, and usage visibility.

### Exit criteria

- Owner/chat authorization precedes model calls or personal-data access.
- Search and extraction preserve provenance; failed or truncated material is identified. Answers distinguish retrieved facts, interpretation, and gaps.
- Reply association retrieves relevant evidence. An unqualified stop targets the foreground run, and cancellation prevents new work after it is processed.
- Ordinary restart preserves accepted messages and conversation state. Duplicate inbound updates do not repeat accepted state changes.
- Enforce tool/path/URL boundaries and configured call/time/output/spending limits from this milestone. Source instructions cannot expand access.
- Keep original messages independently of agent state so later compression has a canonical archive.

### Traceability and evidence

Focus: AUTH-001, CHAT-001, CHAT-002, WEB-001, WEB-002, SEC-001, SEC-002, DATA-001, OPS-001, and OPS-002.

Complete AC-01 and AC-02. Collect the applicable foreground portions of AC-05, inbound/conversation portions of AC-07, reply portions of AC-09, research-boundary portions of AC-10, and limit/usage portions of AC-12. Retain real Telegram/provider evidence, source material, and controlled boundary/restart checks. Background, memory, and full-case outcomes remain pending.

## M2: Deliver recurring briefings

### Outcome and scope

Create a recurring news briefing in natural language, echo its agreement, and receive results in the same chat. Support listing, modification, pause, resume, deletion, and stopping individual runs. Background runs use independent contexts; the task agreement, execution, saved result, and delivery have durable state.

### Exit criteria

- Create one task from an explicit, complete request. Clarify missing timezone or an ambiguous control target before changing state.
- Apply task-scoped preferences without changing global answer style.
- Pause blocks future starts while current work continues; stopping a run is separate from deleting its recurring task.
- Respect configured catch-up rules after downtime, coalescing eligible missed occurrences without flooding the chat.
- Retry transient failures within limits; reuse a saved result after send failure and record uncertain delivery. Do not claim exactly-once sending.
- Recover accepted task changes and run results across restart. Background work does not monopolize foreground conversation and cannot exceed stored authorization.

### Traceability and evidence

Focus: CHAT-002, TASK-001, TASK-002, TASK-003, TASK-004, TASK-005, TASK-006, task-scoped MEM-001, CTX-001, DATA-001, OPS-001, and OPS-002.

Complete AC-03 through AC-07 using the foreground behavior from M1. Extend AC-09 with background/reply behavior, AC-10 with task-authorization checks, and AC-12 with background limits/failure notifications. Evidence includes stored agreements, controlled clock/failure checks, restart observations, and actual Telegram delivery. Memory/compression and other incomplete case portions remain pending.

## M3: Deliver personal memory and context management

### Outcome and scope

Explicitly save, inspect, correct, and forget personal memory. Retrieve relevant entries in conversation and recurring work. Automatically compress older conversation state while retaining originals and keeping task evidence separate from the main dialogue.

### Exit criteria

- Acknowledgements show exactly what was saved or changed, with source, scope, time, and status retained.
- Inferred preferences remain suggestions until accepted; task preferences do not become global automatically.
- Forgotten/superseded entries stop influencing retrieval and are not reconstructed from retained history or cached summaries.
- Forced compression preserves current decisions, corrections, constraints, and complete recent tool interactions. Retained originals remain retrievable.
- Memory, compression, and source content cannot create task authorization or change tool permissions. Relevant memory survives an ordinary restart.

### Traceability and evidence

Focus: MEM-001, MEM-002, MEM-003, CTX-001, CTX-002, SEC-002, DATA-001, and DATA-002.

Complete AC-08 and AC-09. Extend AC-10 with memory/summary attacks and AC-11 with active-memory deletion and re-extraction checks; backup/restore coverage remains for M4. Retain memory/source records, assembled-context inspection, forced-compression checks, and restart observations.

## M4: Accept the first version for personal use

### Outcome and scope

Run the agreed first version through Docker Compose, with all three user journeys, inspectable operations, and verified recovery/data lifecycle behavior. Provide instructions that another reader can follow without knowing the design conversation.

### Exit criteria

- All 22 requirements and AC-01 through AC-12 have complete, linked evidence. Previously partial cases are closed and earlier workflows are regression-checked.
- Verify actual deployment mounts, database exposure, credentials, and resource boundaries. Development-mode checks alone do not establish deployment isolation.
- Validate retention, deletion, backup, and restore, including reconciliation of forgotten memories and deleted tasks before resuming retrieval or scheduling.
- Demonstrate bounded failures, cancellation, restart, missed-run handling, delivery uncertainty, and inspectable usage across the integrated product.
- Add verified setup/tutorial, operational how-to, and configuration reference documentation in English and Chinese. State deployment prerequisites, external service use, and remaining limitations.
- Record a personal-use trial and its findings. The trial duration is to be defined; it does not replace acceptance evidence.

### Traceability and evidence

All requirements; complete AC-01 through AC-12, including DATA-002 and full restore coverage in AC-11. Keep a release acceptance record linking deployment, live service, failure/recovery, and data-lifecycle evidence. Document which environments and providers were actually tested, and identify remaining validation gaps.

## Updating progress

Use `Not started`, `In progress`, `Implemented; verification pending`, or `Verified`. Update both language versions together. A verified milestone records the revision, execution date, tested environment, requirement/case coverage, evidence locations, and known limitations.

Evidence may be redacted records, focused check results, or reproducible manual observations; choose the appropriate form for the claim. Do not store API keys, tokens, or unnecessary personal data. Keep incomplete case portions visibly pending. Reorder or adjust future scope through a documented change while preserving requirement traceability.
