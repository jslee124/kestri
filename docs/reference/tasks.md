# Recurring tasks reference

[简体中文](tasks.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Scope: M2 implementation; validation status is tracked in the [M2 record](../development/m2-validation.md).

## Configuration and schedule

| Variable | Default | Meaning |
| --- | --- | --- |
| `KESTRI_OWNER_TIMEZONE` | Unset | Explicit IANA owner timezone; otherwise each creation must provide one |
| `KESTRI_TASK_LIMIT` | 16 | Maximum non-deleted tasks, including paused tasks; range 1–64 |
| `KESTRI_BACKGROUND_QUEUE_LIMIT` | 8 | Queued/running background executions; range 1–32 |
| `KESTRI_SCHEDULER_INTERVAL_SECONDS` | 5 | Local due-check interval; range 1–60 seconds |

One foreground worker and one background worker operate independently. Both share the M1 call, timeout, output, monthly and per-run cost bounds. A background attempt has the same timeout as foreground research. Task proposal extraction permits at most two model calls and uses the same spending admission. Task listing and slash controls do not require a model, except `/task` requests that require interpretation.

Schedules support daily and weekly local wall-clock times, not arbitrary cron, intervals, one-off reminders, or monthly rules. Use `HH:MM`, or an explicit Chinese clock time such as `早上八点`. Weekly requests name weekdays (Monday=0 internally; lists display Monday=1). `tzdata` supplies a portable IANA fallback. A nonexistent daylight-saving local time is skipped; an ambiguous time runs at the earlier fold once. Instants and occurrence identities are stored in UTC. New, updated, or resumed agreements start at the next future occurrence; resume does not replay the paused period.

## Owner interactions

| Input | Effect |
| --- | --- |
| `每天 08:00 Asia/Shanghai 给我 AI 新闻简报` | Propose and persist one daily agreement; echo ID, content, time, timezone, catch-up policy, and status |
| `每周一 08:00 Asia/Shanghai 给我 AI 新闻简报` | Weekly agreement |
| `/tasks` | List non-deleted task agreements without a model call |
| `/task` | Show task input guidance |
| `/task 暂停任务 TASK_ID` | Interpret and pause the identified agreement |
| Reply to an agreement/briefing: `暂停` / `恢复` / `删除` | Resolve the task through that message |
| Reply: `把这份简报改到 09:00` / `让这份简报更短一点` | Change timing or append an owner-scoped content amendment |
| `/stop RUN_ID` | Stop one identified queued/running execution using an unambiguous 8+ character UUID prefix |
| Unqualified `/stop` | Stop active foreground work; never implicitly stop a background run |
| `/new` | Clear foreground committed context when no foreground work is queued/running; preserve tasks and history |

A sole existing task can resolve an otherwise omitted control target. With multiple candidates, require a reply or task ID/name. Deleted tasks are tombstoned and disappear from `/tasks`; records/evidence remain until a later data-lifecycle implementation. Replies to the combined `/tasks` list do not identify one task. Task preferences never update global answer style or personal memory.

Natural-language routing is intentionally conservative: direct delegation and control phrases in Chinese/English are recognized; quotes, forwarded messages, explanations, and conditional examples cannot grant task authority. Unrecognized wording remains ordinary conversation. Clarifications ask the owner to resend a complete request; there is no multi-step pending-task wizard. Explicit times/weekdays and instruction excerpts are checked independently of the model. Missing timezone, unsupported timing, ambiguous targets, or invalid proposals cause no task mutation.

## Persistence and authorization

PostgreSQL schema migration 2 adds agreements, revisions, task-change records, associations, execution kind, due time, retry attempt, and availability. One database/bot process lock remains required. The scheduler is a local asynchronous loop; PostgreSQL is the schedule authority, without a separate broker or scheduler database.

A task proposal agent receives only the authorized owner's current message and explicitly configured timezone. Its sole structured-output tool is `TaskPlan`; it has no research or filesystem tools. The proposal grants no authority by itself. Application policy checks the direct request and allowed action before an atomic task mutation plus a run-keyed change ledger. Duplicate updates and recovered committed mutations do not repeat changes. If cancellation arrives after a change committed, the persisted agreement is reported rather than falsely claiming that no change occurred.

Research agents, source material, previous answers, and scheduled runs have no task-management tools. Each background run snapshots the stored instruction, timezone, agreement revision, and scheduled instant. It starts with fresh graph context and does not advance foreground checkpoints. A foreground reply to a completed briefing can inspect that result's evidence through the existing scoped read tool.

## Downtime, controls, retries, and delivery

The default per-task catch-up window is six hours. Coalesce all misses into the latest occurrence at most once while eligible; skip expired occurrences and advance to the next future time. Capacity exhaustion leaves due work eligible until its window expires. At most one queued/running execution exists per task. A unique `(task_id, scheduled_for)` constraint prevents duplicate local occurrence creation. Expired queued occurrences are cancelled before claiming; they can be replaced by one eligible recent occurrence after downtime. Decisions are retained as operational events.

Pause, update, and delete cancel queued executions from the old agreement; already-running work continues with its snapshot. Shared transaction lock ordering serializes changes with scheduled starts. After pause acknowledgement no new scheduled work starts for that task. Deleting a task does not revoke an already-submitted external request or erase history. `/stop RUN_ID` is the independent cancellation operation.

Selected transient model/transport errors allow one automatic retry after 30 seconds (two attempts total). Each attempt uses fresh background context; accumulated run cost and unknown reservations remain bounded by the same run budget. Paused/deleted/changed or expired work is not retried. Budget, policy, context, and call-limit failures are terminal. Process-interrupted executions are reported once and are not blindly rerun. Routine scheduled work sends only its final briefing, or one final failure/interruption notice; no per-tool progress is sent.

Results and outbox entries commit before sending. Known non-sends reuse saved text with at most three send attempts; ambiguous sends are quarantined as `uncertain`. This does not provide exactly-once remote delivery. `/status` and `/runs` show kinds, evidence/use counts, safe errors, and failed/uncertain delivery counts. M3 supplies scoped personal memory and compression; see the [memory/context reference](memory-and-context.md). Physical retention, restore reconciliation, and manual resend remain deferred. The application must keep running locally; laptop sleep or stopped Docker delays work.
