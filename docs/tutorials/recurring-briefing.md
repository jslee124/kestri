# Create a recurring briefing

[简体中文](recurring-briefing.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Scope: M2; see the [validation record](../development/m2-validation.md).

## Prepare the running bot

Complete [Telegram setup](telegram-research.md). Keep the local application and PostgreSQL running. Put an explicit IANA zone in the request, or configure `KESTRI_OWNER_TIMEZONE` locally and restart the app. Your computer's timezone is not an implicit agreement.

## Delegate the briefing

Send: `每天 08:00 Asia/Shanghai 给我 AI 和科技新闻简报：最多三项，每项两句话，并附实际读取的来源链接。`

Check the returned agreement: task ID, content, daily time, timezone, status, and missed-run policy. A complete request creates one task without a separate approval question. Missing or unsupported information receives a clarification with no task change; resend the full request after adding it. `/tasks` lists saved agreements.

At the next scheduled time, Kestri runs the stored request in an independent context, then sends the final briefing in the same chat. You can continue chatting while the briefing works. Public sources and budget limits remain those of ordinary research. Sleep, lost connectivity, or a stopped app can delay delivery.

## Change and control it

Reply to the task agreement or its briefing with `让这份简报更短一点`, or `把这份简报改到 09:00`. Inspect the new agreement. Changes belong to that task and do not change your global preferences.

Reply `暂停` to prevent future starts; an already-running briefing continues. Reply `恢复` to enable future occurrences from the next scheduled time. To stop one active background execution, get its execution ID from `/runs` and send `/stop RUN_ID`; stopping does not delete the agreement. Unqualified `/stop` targets foreground work.

Reply `删除` or send `删除任务 TASK_ID` to remove future scheduling. Deleted agreements leave retained history/evidence; there is no physical archive deletion in M2. With multiple tasks, an ambiguous request asks for clarification. Replying to the aggregate `/tasks` listing is not a way to select one task.

## Observe restart behavior

Restart the application with the same PostgreSQL and workspace volumes. Agreements survive. The default six-hour catch-up rule produces at most one recent missed briefing per eligible task, instead of replaying all missed days. Older misses are skipped. Paused/deleted tasks do not catch up.

Use `/status`, `/runs`, and `/usage` to inspect results and estimates. Known send failures retry saved text; ambiguous sends stay uncertain for inspection. A process-interrupted research run is reported instead of blindly restarted. See the [task reference](../reference/tasks.md) for exact limits, retry and daylight-saving behavior.
