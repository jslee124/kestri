# Task recognition, agreements, and scheduling algorithms

[简体中文](task-scheduling.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Implementation: [task_intent.py](../../src/kestri/tasks/intent.py), [task_agent.py](../../src/kestri/tasks/agent.py), [tasks.py](../../src/kestri/tasks/service.py), [schedule.py](../../src/kestri/tasks/schedule.py), and claim/finish paths in [store.py](../../src/kestri/storage/store.py). Commands/defaults are maintained in the [task reference](../reference/tasks.md) and [CLI reference](../reference/cli.md).

## Deterministic intent routing

`task_intent(text, task_reference=False)` returns `create`, `update`, `pause`, `resume`, `delete`, `list`, or `None`; it is a regex recognizer, not an LLM classifier. It trims the request and strips an exact leading `/task ` before recognition. `/task` alone remains guidance. Recognition occurs on direct authorized input; application routing disables task intent for forwarded/external-reply messages.

The recognizer rejects code fences, selected quotation markers, and explanatory/conditional phrases such as Chinese explanation/translation/example/how/if language and English `explain`, `translate`, `example`, `how to`, `if `. Creation requires recurring wording, delegation wording, a permitted leading form, and no leading update/control wording. Control requests require a permitted leading form, an action match within the first 20 characters, and either explicit `/task`, a reply association, or task/briefing vocabulary.

Control precedence is delete, pause, resume, update, list. This matters when a request mentions multiple actions. Unsupported or unmatched text routes to ordinary research rather than creating a pending task. Clarification is a result, not a durable multi-turn form; the owner must send a new complete instruction.

| Example | Recognition / independent validation |
| --- | --- |
| `每天 08:00 Asia/Shanghai 给我 AI 新闻简报` | `create`; proposed fields still checked before mutation |
| `解释每天 08:00 的任务怎么运行` | No delegation; ordinary research |
| `/task 暂停任务 UUID_PREFIX` | `pause`; target must resolve uniquely |
| Reply to a task: `暂停` | `pause` because a reply supplies task-reference context |
| `暂停` without task context | No task intent; not a global pause operation |
| `每周给我新闻简报` | May recognize create, but schedule lacks explicit weekday/time and must clarify |

## Proposal schema and model role

`TaskAgent` recomputes permitted intent, supplies the current request or validated bounded direct-owner clarification chain, plus configured owner timezone, and registers `ToolStrategy(TaskPlan, handle_errors=False)` with no research tools. It allows at most one model call, uses `BoundsMiddleware` spending/input checks, and shares the run timeout. No saver, personal memory, or old dialogue is supplied.

| `TaskPlan` field | Constraint / interpretation |
| --- | --- |
| `action` | One control action or `clarify`; must match permitted intent unless clarifying |
| `target`, `title` | Optional string, at most 100 characters |
| `instructions` | Optional string, at most 4000 characters for this proposal |
| `local_time` | Optional `HH:MM` matching a 24-hour clock |
| `timezone` | Optional string up to 100 characters, validated by `ZoneInfo` |
| `weekdays` | Optional list of 1–7 distinct values 0–6, returned sorted |
| `clarification` | Optional string up to 500 characters |

Extra fields are forbidden. Unlike web tool schemas, this model is not configured globally strict; application policy independently checks the resulting values. Null update fields preserve previous values. A title is display metadata; it does not itself authorize new instructions or tools.

## Agreement mutation transaction

`TaskService.apply()` requires `run.kind='task_control'`, re-recognizes request intent, and rejects action mismatch. It locks the owner conversation then the active run, rejects inactive/cancelled work, and returns a prior `task_changes` result if that run already committed a proposal.

Creation requires instructions, explicit recognized time/weekdays, and either a requested IANA zone or configured owner zone. A proposed timezone must appear in the request or equal the configured zone. Content instructions must be an exact contiguous substring of the owner request. It bounds nondeleted task count, generates a UUID, defaults an omitted title to `个人简报`, fixes catch-up at 21600 seconds, and calculates the next future occurrence. The new task is `active`, revision 1.

For controls, candidates are this owner's nondeleted tasks under row locks. Resolution prioritizes a reply: join the referenced archived message/run and use `COALESCE(messages.task_id, runs.task_id)`. Without a reply, an explicit target must occur in owner text and match a UUID prefix or exact title. Without either, only a single candidate can resolve. A reply to a combined list is not a task selector.

Update must change at least one field. New content must be an owner-text substring and is appended as `\n用户修订：...`; it does not replace earlier instructions. Changed time/weekdays must match deterministic request parsers; changed timezone must occur in the text. Repeated amendments have no separate aggregate length cap in the current implementation; model input admission remains the later bound. Pause/resume/delete set task status; they do not stop a running execution.

Each successful update/control recomputes a future `next_due`, increments `revision`, and cancels queued task runs with `AgreementChanged`. Explicit resume also clears `restored`. Mutation stores the task ID on its control run and writes a redacted acknowledgement into `task_changes` before returning. Even clarification/list/no-mutation results can have an acknowledgement row; its presence means the command result committed, not necessarily that a task was created.

`TaskAgent` finalizes the run separately. If an exception/cancellation races with a committed change, `Store.finish()` retrieves the authoritative acknowledgement rather than falsely reporting rollback. Duplicate acceptance and repeated apply do not produce a second agreement.

## Clock parsing and occurrence calculation

`requested_time()` first searches numeric `H:MM`/`HH:MM`; if found, it returns zero-padded `HH:MM`. Otherwise it recognizes Chinese digits/`两`/`十`, `点`, optional `半` or minutes, and adds 12 for afternoon/evening wording when the hour is below 12. Invalid hours/minutes return `None`. It is a bounded parser, without free-form relative-date or English prose-time inference.

`requested_weekdays()` prioritizes weekday wording (Monday–Friday), then daily wording (all seven days), then explicit Chinese or English weekday names. It deduplicates and sorts. Generic weekly wording without day names is insufficient.

`occurrence(day, local_time, timezone)` constructs local wall time with `fold=0`, converts to UTC, and round-trips to local wall time. A failed round-trip means a nonexistent DST time and returns `None`; an ambiguous time uses the earlier fold once. `next_occurrence()` scans at most 15 local calendar days and requires a candidate strictly after its input instant. `latest_occurrence()` scans backward at most 15 days and requires a candidate at or before now. Exhausting the search raises a safe failure rather than inventing a time.

## Due-check algorithm and queue capacity

`tick(now=None)` accepts an injected clock for tests; the application uses current UTC. Inside a transaction it locks the owner conversation, cancels expired queued background work, locks due active tasks ordered by `next_due`, and counts all queued/running background work for global capacity.

For each due task:

1. Find the latest scheduled occurrence and compare with persisted `next_due`.
2. Compute its age and check the six-hour window; check whether this task already has queued/running work.
3. If eligible, idle, and capacity is exhausted, leave `next_due` unchanged so the next tick can reconsider until expiry.
4. If eligible, idle, and capacity exists, insert a background run using the stored instructions, UTC occurrence, timezone, task ID/revision, and unique occurrence identity. No foreground acknowledgement is generated.
5. Otherwise coalesce while busy or skip an expired occurrence. Advance `next_due` to the next future occurrence and record `schedule_decision` (`queued`, `coalesced_busy`, or `skipped_expired`).

An example: the application wakes after three daily misses. It schedules only the latest occurrence if within six hours, not three catch-up jobs. If that occurrence is seven hours old, it skips it. If the queue is full while still eligible, it waits; it does not extend the authorization window.

## Claim, retries, pause, and restart

Background `claim_run()` locks conversations and revalidates queued work against active status, current revision, and catch-up deadline. Invalid work becomes cancelled with `CatchUpExpiredOrChanged`. Claim captures the current memory epoch, sets no foreground source thread, and starts one worker execution. Task instruction snapshots do not silently follow later agreement edits.

| Change / failure | Effect |
| --- | --- |
| Pause/update/delete commits | Cancel queued old-agreement work; already-running snapshot continues |
| Resume | Future occurrence only; no paused-period replay |
| `/stop RUN_ID` | Cancel one queued/running run independently of task lifecycle |
| Transient failure | One retry after 30 seconds if active and same revision; claim also rechecks expiry |
| Budget/policy/context/call limit | Terminal; no automatic retry |
| Process interruption | Saved interruption notice; no automatic graph replay |
| Restored agreement | Paused and flagged restored; requires explicit resume |

The exact retry allowlist is `APIConnectionError`, `APITimeoutError`, `RateLimitError`, `InternalServerError`, `ConnectError`, `ConnectTimeout`, `PoolTimeout`. This is class-name matching in `Store.finish()`, not “retry every 5xx or tool failure.” Retry keeps the run ID and accumulated spend, increments attempt to 2, and uses a new graph thread. Saved result delivery has a separate retry policy.

## Verification and change rules

[Schedule tests](../../tests/tasks/test_schedule.py) cover deterministic clock/DST parsing; [task integration tests](../../tests/tasks/test_tasks_integration.py) cover duplicate mutation, catch-up/capacity, task targeting, cancellation races, pause/resume, revision changes, and background independence. A changed recognizer/parser must retain negative authorization cases, not merely add successful examples. New schedule types require changes to schema, proposal policy, deterministic parsing, occurrence identity, recovery, and bilingual command documentation together.
