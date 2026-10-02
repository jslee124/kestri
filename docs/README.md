# Documentation guide

[简体中文](README.zh-CN.md) · [Project home](../README.md)

Updated: 2026-10-02. Status: M0, M1, M2, M3, and M4 complete first-version delivery acceptance; long-term use is recorded separately.

## Embedding and next memory increment

- [Beijing embedding connection](reference/embedding.md): implemented settings, adapter, and independent smoke.
- [Connection validation](development/embedding-validation.md): live evidence and limits.
- [Memory v2 specification](design/memory-v2.md): automatic facts, semantic recall, history tools, and lifecycle; automatic extraction implemented, hybrid retrieval implemented, lexical history tools implemented, progressive hybrid history implemented, background coverage/evaluation pending.
- [Memory v2 progress](development/memory-v2-progress.md): extractor and durable runtime implemented; semantic recall pending.
- [ADR-0007](decisions/0007-automatic-semantic-memory.md): automatic and semantic memory direction.

## First-version use and operations

- [First-version acceptance](development/first-version-acceptance.md): all requirements, cases, and evidence boundaries.
- [Operations](how-to/operate-local-agent.md): startup, inspection, restart, and cleanup.
- [Backup and restore](how-to/backup-and-restore.md): private snapshots and empty-target recovery.
- [Data lifecycle reference](reference/data-lifecycle.md): interfaces, retention, and quarantine.
- [ADR-0006](decisions/0006-conservative-data-recovery.md): recovery tradeoffs.

## Start using the implemented increment

- [Personal memory](tutorials/personal-memory.md): save, correct, forget, and inspect originals.
- [Memory and context reference](reference/memory-and-context.md): retrieval, invalidation, compression, and limits.
- [M3 validation record](development/m3-validation.md): controlled checks, real DeepSeek compression, and Telegram restart/forget observations.

- [Recurring briefing](tutorials/recurring-briefing.md): create, manage, and receive a daily/weekly briefing.
- [Task reference](reference/tasks.md): agreements, scheduling, background execution, and recovery rules.
- [M2 validation record](development/m2-validation.md): controlled checks and live scheduling/delivery evidence.

- [Telegram research](tutorials/telegram-research.md): owner setup and the first product workflow.
- [M1 reference](reference/telegram.md): controls, persistence, deployment, and bounds.
- [M1 validation record](development/m1-validation.md): offline, live-service, and deployment evidence.
- [First agent run](tutorials/first-agent-run.md): a guided live model/tool exercise.
- [Run offline checks](how-to/run-checks.md): validate a development change.
- [M0 configuration](reference/configuration.md): exact implemented settings and results.
- [M0 validation record](development/m0-validation.md): evidence and known limitations.

## Study the implementation

Start with the [implementation guide](development/implementation-guide.md): every Python module and function/method entry point, SQL, engineering configuration, and test responsibility, with links to the owning detailed document.

- [CLI and complete configuration](reference/cli.md): commands, arguments, exit codes, settings classes, and defaults.
- [Execution and delivery](design/execution-and-delivery.md): input authorization, archiving, queues, cancellation, recovery, and outbox states.
- [Tasks and scheduling](design/task-scheduling.md): intent detection, proposal validation, mutation transactions, timezones/DST, catch-up, and retries.
- [Model and accounting](design/model-and-accounting.md): request adaptation, middleware, usage, reservation/settlement, and error classification.
- [Data maintenance internals](design/data-maintenance.md): locks, snapshot format, validation, restore transformations, cleanup, and failure boundaries.

## Read the design

| Document | Purpose | Status |
| --- | --- | --- |
| [Product](design/product.md) | Positioning, user journeys, and first-version scope | Accepted product direction |
| [Requirements](design/requirements.md) | Identified requirements and acceptance criteria | Accepted first-version specification |
| [Architecture](design/architecture.md) | Deployment, module map, concurrency, complete request flows, and recovery | Implemented software architecture |
| [Database](reference/database.md) | Tables, fields, relationships, indexes, transactions, and checkpoint storage | Implemented schema reference |
| [Context management](design/context-management.md) | Run seeding, prompt composition, memory selection, compression, and epoch revocation | Implemented context design |
| [Tool design](design/tools.md) | Capability sets, schemas, adapters, URL/file boundaries, evidence, and accounting | Implemented tool design |
| [Security and data](design/security-and-data.md) | Permissions, isolation, memory, context, and data lifecycle | Implemented first-version boundary design |
| [Runnable milestones](development/milestones.md) | Runnable increments, exit criteria, requirement coverage, and evidence | M0, M1, M2, M3, and M4 verified |
| [ADR-0001](decisions/0001-agent-stack.md) | Python, LangChain Agent, and DeepSeek official API | Accepted |
| [ADR-0002](decisions/0002-local-deployment-and-tool-boundaries.md) | Local deployment and controlled tools | Accepted |
| [ADR-0003](decisions/0003-persistence-and-state-separation.md) | PostgreSQL and separation of state categories | Accepted |
| [ADR-0004](decisions/0004-recurring-task-execution.md) | Durable agreements, local scheduling, and independent execution | Accepted |
| [ADR-0005](decisions/0005-explicit-memory-and-revocable-context.md) | Explicit memory, epoch invalidation, and budgeted summaries | Accepted |

“Accepted” records a design decision. It does not establish that its implementation works. The requirements document is the source of acceptance criteria; [M0 evidence](development/m0-validation.md) covers initial model/tool integration; [M1 evidence](development/m1-validation.md) separately tracks the product workflow.

## Documentation organization

Kestri uses [Diátaxis](https://diataxis.fr/) to distinguish learning tutorials, task-oriented how-to guides, factual reference, and explanations. Product requirements, delivery milestones, and ADRs are maintained separately as engineering records. This directory layout is a project convention, not a requirement imposed by Diátaxis.

| Category | Reader need | Availability |
| --- | --- | --- |
| Tutorials | Learn by completing a guided experience | First agent run, Telegram research, recurring briefing, and personal memory available |
| How-to guides | Complete a specific task | Development checks, operations, and backup/restore available |
| Reference | Look up exact interfaces, configuration, and behavior | M0 configuration, M1 Telegram, M2 tasks, and M3 memory/context, and M4 data reference available |
| Explanation | Understand concepts, mechanisms, and tradeoffs | Source-grounded architecture, context management, and tool design available |
| Design | Review intended product behavior and system boundaries | Available above |
| Development | Follow runnable delivery increments and verification progress | Milestones, M0, M1, M2, M3, and M4 evidence available |
| Decisions | Understand why a major choice was made | Available above |

Do not present a proposal as reference documentation for an implemented feature. Tutorials and reference describe only verified implementation; future capabilities remain in the design.

## Language and maintenance

- English is the primary source. Each `name.md` has a sibling `name.zh-CN.md` translation; `README.md` follows the same rule.
- Each pair links to its counterpart. Chinese navigation links to Chinese documents; English navigation links to English documents.
- Update both versions in the same change. Preserve requirement IDs, decision IDs, technical identifiers, and the meaning of dates and statuses.
- If a translation diverges, correct the pair; do not retain different requirements in different languages.
- Keep headings, scope, tables, and acceptance cases aligned. Translate prose, while preserving exact API identifiers and paths when relevant.
- Store each normative fact in one designated document and link to it elsewhere. Product defines scope, requirements define acceptance, design documents explain mechanisms and defaults with explicit implementation status, and milestones define delivery order and evidence status.
- Label confirmed decisions, adjustable defaults, open questions, implemented behavior, and verification evidence distinctly.
- Cite primary sources for external technical capabilities and record when they were checked. Recheck drifting provider facts during implementation.

## Decision records

ADRs use a numbered filename and record status, context, decision, alternatives, consequences, and review conditions. Record significant choices; routine tuning values belong in design documents. A replacement ADR identifies the decision it supersedes, and both translations are updated.

## Verification policy

Before accepting a documentation change, check local links, English/Chinese pairing, identifier consistency, and formatting. Once software exists, connect acceptance criteria to actual validation evidence. Distinguish offline checks, live API behavior, recovery tests, and deployment acceptance.

- [Semantic memory runtime](reference/semantic-memory.md): implemented vector indexing/hybrid recall, owner switches, currency accounting and optional deployment; live quality remains unverified.

- [Bounded chat history tools](reference/history-retrieval.md)

- [Repository layout](development/repository-layout.md)
