# First-version acceptance record

[简体中文](first-version-acceptance.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02.

Status: M4 first-version flow acceptance verified on 2026-10-02. The owner explicitly selected delivery after the session trial, with long-term daily use recorded separately. This record closes development scope; it does not claim long-term reliability or cross-platform qualification.

## Revision, environment, and checks

Branch `codex/m4-first-version`, based on main `f82db3a23ba03f441ed3859c55f2f996e7715f2b`. Python 3.14, uv 0.12.3, macOS host, OrbStack Docker/Linux arm64, PostgreSQL 17; deployed Python 3.14.8. Locked LangChain 1.4.3 and LangGraph 1.2.12 remain unchanged. The source wheel includes migrations 1–4. Ruff lint/format, strict mypy, bilingual/link checks, package build, and 122 tests pass with an isolated real PostgreSQL database and **no skips**. Implementation revision [`4c082ec`](https://github.com/jslee124/kestri/commit/4c082ecb83e34bdd1d515a7bae405202190dc42d) passed both exact-revision [push CI](https://github.com/jslee124/kestri/actions/runs/36959236660) and [PR CI](https://github.com/jslee124/kestri/actions/runs/36959239867) on Linux/Python 3.14 with disposable PostgreSQL and no live credentials. [Draft PR 5](https://github.com/jslee124/kestri/pull/5) contains the implementation and this evidence record; main is not merged.

M4 adds 12 lifecycle cases: real business/evidence roundtrip; later-forgotten/deleted state in an older backup; explicit reauthorization; physical expiry of archive/checkpoint/file copies; content erasure preserving cost/identity and unrelated files; active-lease/busy refusal; incomplete evidence/export rejection; corrupt/private-file validation; controlled file-failure rollback; independent backup expiry; one-time restored pending-command discard; retry after failed unlink; symlink boundaries; and cancellation retaining the backup lease until file work finishes. Some cases contain multiple transitions. The entire earlier suite runs again.

Controlled external failures use actual application/adapter/runtime code with mock transports and clocks. They cover specified failure transitions, not every power-loss point, real provider outage, or security attack. The initial database test attempt failed setup while Docker was stopped; after starting it, the full isolated suite passed. No personal database was used for destructive tests.

## Actual deployment and recovery

[Sanitized M4 metadata](evidence/m4-live.json) records health, non-root/read-only policy, mounts, network/port and resource checks, menu readback, and workflow outcomes. Actual run identifiers, precise timestamps, charges, personal database statistics, and bodies are retained only in the local private acceptance directory, not published. Actual base Compose publishes no database port, mounts only the dedicated workspace into the app, has no home/socket mounts, drops capabilities, and applies CPU/memory/process/tmp limits. Both services are healthy and use `unless-stopped`; this does not establish computer startup or provider health.

The stopped application created a private logical backup from its real existing data. It was restored into a **separate empty database and workspace**, with business records and extracted evidence matching their source content. Dry run imported nothing; mode was `0600`; no imported work or delivery remained executable. [Restore metadata](evidence/m4-restore.json) contains check outcomes, not the private snapshot or personal database statistics. Existing snapshot facts/tasks were already forgotten/superseded/deleted: active-state quarantine and later-revocation protection are additionally established by controlled fixtures. The isolated recovered Telegram poller was not started; its pending-update boundary is transport-tested. Personal deployment data was preserved.

## Session personal-use trial

The owner Telegram chat saved one temporary global preference requesting the briefings end with “验收完成”. A real DeepSeek/Tavily research request extracted official LangChain sources, included links and retrieval limitations, and applied that memory. A Telegram reply to the answer distinguished source facts from engineering judgment, without new web searches.

One temporary daily agreement was created for an imminent occurrence in an explicit local timezone. The application was ordinarily restarted before that occurrence; the agreement and current memory persisted. Exactly one background briefing ran and was delivered at the scheduled occurrence, with retrieved source links and the memory suffix. The temporary task was paused and deleted afterward, and the temporary memory forgotten. Final `/tasks` and `/memory` checks show no active validation entries; no queued/running work remains. The local estimate is retained privately; it is not a provider invoice.

This is a session-flow trial, not days of continuous use. Long-term usefulness, sleep/wake behavior across repeated days, provider reliability, summary quality across varied conversations, and personal feedback remain an ongoing trial record. No completion claim is based on waiting for an arbitrary trial duration.

## Requirements and acceptance traceability

All rows below are verified **within the stated first-version outcomes and evidence classes**. Historical M0–M3 evidence remains dated; this suite regression-checks their source behavior.

| Cases | Requirements | Evidence |
| --- | --- | --- |
| AC-01 | AUTH-001, SEC-001 | [M1](m1-validation.md), authorization/identity and direct-boundary tests |
| AC-02 | CHAT-001, WEB-001, WEB-002 | M1 and session live research/reply, extraction failure/truncation fixtures |
| AC-03 | TASK-001, MEM-001 | [M2](m2-validation.md), complete agreement/timezone/task-scope tests, session agreement |
| AC-04 | CHAT-002, TASK-002 | M2 reply/ambiguous-target/change tests, session pause/delete |
| AC-05 | CHAT-001, TASK-003 | M1/M2 cancellation and active-pause/scheduling tests; session controls |
| AC-06 | TASK-004, TASK-005 | M2 deterministic catch-up/window tests and restart observation; session ordinary restart |
| AC-07 | TASK-006, DATA-001 | M1/M2 acceptance/result/delivery failure-injection and recovery, live saved delivery |
| AC-08 | MEM-001, MEM-002, MEM-003 | [M3](m3-validation.md), explicit/inferred/revoked memory tests, real save/correct/restart/forget |
| AC-09 | CHAT-002, CTX-001, CTX-002 | M1/M2 independent contexts and replies; M3 archive/checkpoint and real compression; session reply |
| AC-10 | TASK-004, SEC-001, SEC-002 | M1/M2/M3 source/summary attacks, URL/path/direct-tool policy and authorization tests |
| AC-11 | MEM-003, DATA-002 | M3 active revocation, M4 physical retention/erase/old-backup quarantine/expiry/file rollback fixtures and real isolated restore |
| AC-12 | WEB-002, OPS-001, OPS-002 | M0–M3 call/time/output/input/cost/provider-failure bounds, notification and delivery tests, session usage/status |

The table covers all 22 requirement IDs. [Requirements](../design/requirements.md) remain the acceptance source. Full evidence does not mean every case was reenacted against live external outages; controlled failure cases and live success cases remain separate.

## Delivery and known limits

Use [setup](../tutorials/telegram-research.md), [operations](../how-to/operate-local-agent.md), [data reference](../reference/data-lifecycle.md), and [backup/restore](../how-to/backup-and-restore.md). All documents have Chinese counterparts. The first version is a single-owner Telegram product with controlled tools, local data, and external model/search/messaging. Arbitrary code/desktop control, multi-user GUI/TUI, additional providers, semantic memory extraction, vector search, manual uncertain-send replay, encrypted remote backups, and pinned-result storage are outside this version.

Restore is conservative and loses old context/automatic authorizations; backups are private but unencrypted and bounded. Provider billing/data retention, Telegram history, off-device copies, all abrupt crash points, long-term use, and other host architectures/platforms remain distinct limits. No VM-level or absolute security guarantee is claimed. Publication is for review; merging main remains a separate action.
