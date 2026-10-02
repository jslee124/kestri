# Remember, correct, and forget a preference

[简体中文](personal-memory.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Scope: M3, after the [Telegram setup tutorial](telegram-research.md).

## Save and use a preference

Send `/remember 我希望回答使用简短中文。` to your bot. Check the acknowledgement's exact content, global scope, ID, source, and times. Saving resets active foreground context, preserving original history. Ask a normal question; the model can use the current explicit preference. `/memory` inspects active entries without a model call. Inferred suggestions are not saved; accepting one means issuing your own complete `/remember` request.

For an existing task, use `/remember task TASK_ID 这项简报最多三句话。`. It applies only to that task's future runs, not global style or task timing. To revise the task agreement itself, use the [task controls](../reference/tasks.md).

## Correct and forget

Copy the ID from `/memory`. Send `/correct MEMORY_ID 我希望回答使用详细中文。`. Inspect the new acknowledgement and ID: the old entry is superseded, not silently overwritten.

Send `/forget NEW_MEMORY_ID`. Check `/memory`: the entry is absent. A later question must not use the old entry through automatic history/summary reconstruction. These changes reset active conversation; old reply-associated results cannot bypass the epoch boundary. Original records remain explicitly inspectable through `/history`, then `/history RECORD_ID` and the displayed continuation if needed. Viewing history does not make it active memory.

Restart with `docker compose restart app`, then inspect `/memory` again. Active entries and deletion markers persist in the database volume. Do not use `down -v` for routine restart.

## Continue a long conversation

Continue ordinary conversation. Near 70% of the configured input admission budget, Kestri summarizes older history while retaining recent complete tool interactions. Original messages stay in the archive. `/runs` and `/usage` retain outcomes and summary spending. A failed/oversized summary stops safely; `/new` starts fresh context without forgetting personal memory.

For optional expiry, see [memory/context reference](../reference/memory-and-context.md). Do not store API keys or passwords. Forgetting is removal from active retrieval, not deletion of Telegram messages, historical copies, or backups. M4 provides separate [data lifecycle controls](../reference/data-lifecycle.md).

## Learn from ordinary dialogue

After deploying this feature branch, send `/memory auto on`, then state a direct preference/goal normally. Let foreground work finish; inspect `/memory`, `/memory pending` and `/memory changes`. Confirm a desired candidate with `/correct ID full-content`, or dismiss it with `/forget ID`. `/memory auto off` prevents new extraction; existing facts remain usable. Old conversations are not backfilled. This uses DeepSeek; semantic recall with DashScope embeddings remains pending. See [runtime progress](../development/memory-v2-progress.md).
