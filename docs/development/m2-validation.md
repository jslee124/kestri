# M2 validation record

[简体中文](m2-validation.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Status: M2 verified for daily/weekly recurring briefings, combining controlled failure checks and one owner-authorized live task. Later memory, compression, and data-lifecycle acceptance remain pending.

## Revision and environment

Work branch: `codex/m2-recurring-briefings`, based on `fe04df6`. Local environment: macOS, Python 3.14.7, uv 0.12.3, OrbStack Docker/Linux arm64, and PostgreSQL 17. Core agent dependencies remain at the M1 locked versions; `tzdata` 2026.4 was added. The live restart test used image `sha256:3d3b0804af74a3edaebdfff332febc807271fcb6ed36a156fed70a48cd874202`. Subsequent SQL formatting preserves identical string constants, and the final menu description distinguishes stopping a run from pausing a task. Final deployment successfully restarted image `sha256:f6953e2effe9af754fff3db385df506ca307f30e383b92f97c127a2768b27639` with no remaining recurring tasks. Remote CI status and the final implementation revision are recorded after publication.

## Controlled checks

92 tests pass against an isolated disposable PostgreSQL database, with no skips. Ruff lint/format and strict mypy pass. Actual LangChain structured-output serialization is exercised with mocked DeepSeek responses; the task planner exposes only `TaskPlan`, with no research tools or conversation history.

New checks cover atomic agreement creation, duplicate updates and concurrent application; recovery after task mutation but before acknowledgement; missing timezone/time/weekdays and invented instructions/targets; quoted, forwarded, conditional, and explanatory requests; task-scoped amendments and reply-selected timing changes among multiple tasks; ambiguous deletion; pause during running work, resume, deletion of queued work; independent foreground/background workers and checkpoint heads; foreground stop versus explicit background stop; daily/weekly and daylight-saving scheduling; multiple misses, expired windows, stale queued work and repeated ticks; bounded transient retry; cancellation after an already-committed mutation; saved background result/send retry and uncertain-send quarantine across recovery. M1 authorization, URL/path, spending, cancellation, and research checks remain passing.

Controlled failure injection establishes the tested state transitions. It does not establish real network-outage behavior, arbitrary crash-point coverage, distributed scheduling, or immunity to every model-level prompt injection.

## Live task and restart

With explicit owner authorization, one temporary daily task requested a three-sentence briefing from LangChain official public material, with sources and an explicit `Asia/Shanghai` timezone. The real DeepSeek official API created its agreement; Telegram echoed it. Pause, timing modification, and resume were applied through actual owner messages, reaching active revision 4 with a 20:43 local due time.

The application was stopped at 12:40:25 UTC and restarted after the 12:43:00 UTC occurrence. At 12:43:33 UTC, exactly one background run started from the stored revision 4 agreement. It used fresh graph context, performed real DeepSeek/Tavily work, persisted a completed result, and sent it once through Telegram. `/tasks` responded while that work was running. The briefing included three main sentences, sources, and retrieval/truncation limitations. The source-status appendix was longer than desirable; concise presentation remains a product refinement, and fetched news claims are not independently fact-checked by this validation.

Immediately after delivery, an owner message deleted the task, leaving revision 5 marked `deleted`. `/tasks` reported no tasks. Database inspection confirmed exactly one background run, zero non-deleted tasks, and zero queued/running background runs. A real reply to the completed briefing then distinguished successful extraction, failed extraction, and search-only material without another retrieval call. Task deletion preserves these archived records.

The local estimate for the five task-control calls and one scheduled run was $0.067842; the evidence follow-up added $0.004317. Total observed validation estimate: $0.072159, below the authorized $0.50 limit. These are configured local estimates, not provider invoices. [Sanitized live metadata](evidence/m2-live.json) preserves run identities, timing, status, usage, and delivery state without credentials, owner/chat IDs, full messages, reasoning, or source text. The native Telegram menu visibly contained all nine supported commands, including `/runs`, `/tasks`, and `/task`.

## Persistence and deployment

Schema migration 2 is additive and rerunnable. Application startup migrated the existing M1 database and retained its records. Agreements and change ledgers are independent of LangGraph checkpoints. Background execution snapshots agreement revision/time/instructions, and results plus outbox records commit before transmission. The live restart retained the task agreement and the missed due time. The wheel contains both SQL migrations.

Compose continues using the M1 non-root/read-only application and dedicated workspace/database named volumes, with no home directory or Docker socket access and no published database port. A local app must remain running to execute on time. This record covers Linux arm64 containers on the tested macOS host, not a VM boundary, arbitrary code execution, other host platforms, or per-tool sandboxes.

## Requirement and case coverage

M2 covers CHAT-002, TASK-001 through TASK-006, task-scoped MEM-001, CTX-001, DATA-001, OPS-001, and OPS-002. AC-03 through AC-07 are verified by combining the controlled cases above, the real agreement/control/delivery/restart observations, and the foreground evidence retained for M1. Failure and uncertainty outcomes are controlled observations; the real send succeeded on its first attempt.

AC-09 gains background isolation, foreground availability, and a real briefing-associated evidence follow-up; compression remains pending in M3. AC-10 gains separate task authorization and source-free proposal handling; memory/summary attacks remain pending. AC-12 gains background retry/terminal-state and shared resource-limit coverage. AC-08 and AC-11 remain pending. This does not claim complete first-version acceptance.

## Limits and next increment

M2 supports daily/weekly wall-clock rules and a fixed six-hour creation catch-up policy. It uses conservative instruction routing and requires a full replacement request after clarification; no multi-turn pending-task wizard, one-off reminder, arbitrary cron, distributed worker, manual resend reconciliation, or restore procedure is implemented. Already-running work continues after task pause/deletion unless explicitly stopped; uncertain sends are not automatically replayed. Provider-side work already submitted cannot be revoked by local cancellation.

M3 adds explicit personal memory and managed conversation context. Retention enforcement, backup/restore, and broader deployment/personal-use acceptance remain M4 work. Keep runtime secrets and private state outside public validation artifacts.
