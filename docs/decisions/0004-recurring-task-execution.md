# ADR-0004: Local recurring-task execution

[简体中文](0004-recurring-task-execution.zh-CN.md) · [Documentation](../README.md)

Date: 2026-10-01. Status: accepted for M2.

## Context

M2 adds owner-delegated recurring briefings, with changes, downtime recovery, independent contexts, and bounded spending. Kestri already uses PostgreSQL, an asynchronous local process, and a durable outbox. There is no need for arbitrary cron rules or a fleet of distributed workers.

## Decision

Use PostgreSQL agreements and execution records as the single durable scheduling authority. A local asynchronous loop checks due daily/weekly wall-clock schedules with explicit IANA timezones. Transactional locking and unique occurrence identities serialize task changes and starts; misses are coalesced through the stored catch-up policy.

Run one foreground worker and one independent background worker. Snapshot task instructions and revision; do not continue or advance main-chat graph context. Reuse the existing bounded research tools, cost ledger, and outbox. Limit selected transient background errors to two attempts, with fresh attempt context.

Interpret direct owner task requests in a separate LangChain structured-output agent using `ToolStrategy(TaskPlan)`. Expose no web or host tools there. Validate proposals and persist a run-keyed mutation ledger in application code; never give source text or background research task-write capabilities. Conservative routing and explicit time/weekdays checks prioritize explainable authority over accepting every wording. Clarification asks for a complete replacement request.

## Alternatives

APScheduler could provide broader triggers, but would add a scheduler store and synchronization contract alongside agreements/runs. Celery or an external workflow service would add broker/process/deployment overhead. Arbitrary cron would enlarge timezone and authorization complexity. These are deferred until actual requirements exceed the small local daily/weekly workflow.

## Consequences and review

The local app must stay running; sleep delays execution. PostgreSQL and the outbox provide durable state, not exactly-once remote delivery. DST gaps are skipped and folds use the earlier instant once. Resume schedules future occurrences. M2 supports one owner and one bot process; multiple distributed schedulers are not claimed.

Revisit if users need arbitrary triggers, many concurrent workers, durable multi-step workflows, or broader natural-language control. Keep task authorization, canonical messages, research evidence, and graph state separate when replacing the scheduler.

Sources checked 2026-10-01: [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output), [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html). These describe building blocks; the locking and authorization decisions above are Kestri's design.
