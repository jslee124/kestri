# Conversational assistant controls

[简体中文](assistant-controls.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-03. Implemented interfaces; deployment evidence is recorded separately.

## Everyday controls

| Say or send | Result |
| --- | --- |
| `我有哪些任务？` / `/tasks` | Five agreements per page, with detail and next-page buttons |
| `你现在在做什么？` / `/status` | Current queued/running work |
| `查看最近执行记录` / `/runs` | Latest five executions; `/runs inspect ID` shows one unique execution |
| `本月花费` / `/usage` | Local USD estimates and reservations for the UTC month |
| `停止当前执行` / `/stop` | Stop foreground execution; task pause is a separate operation |
| `开始新话题` / `/new` | Reset committed context and pending choices when foreground work is idle |
| `你能做什么？` / `/help` | Examples and read-only navigation |

These queries use deterministic routing without a model call. Natural phrasing is bounded, not a promise to interpret every sentence. Existing [memory controls](memory-assistant.md) use the same entry point and retain their own policy checks.

## Task conversation

Create a daily or weekly task with explicit time, content and an IANA timezone, unless `KESTRI_OWNER_TIMEZONE` supplies the timezone. For example: `每天早上八点 Asia/Shanghai 给我 AI 新闻简报`. Task interpretation permits one model call and only a structured `TaskPlan`; it has no research, shell or configuration tools. Application checks the requested action and literal owner timing/content before writing.

Ambiguous targets display up to five numbered choices. Click a choice or reply `第二个`; the pending action applies only to that selected revision. Missing timing/timezone can be supplied as `晚上八点` or `Asia/Shanghai`. At most three archived direct-owner control messages form a clarification chain, valid for ten minutes. Unrelated conversation cannot fill missing fields. After a successful change, an explicit timing follow-up such as `改到晚上九点` can target that same revision within ten minutes; an ordinary conversation clears this reference. Bare times cannot modify a completed agreement.

A restart preserves pending choices. Changed targets, expired choices, missing/expired source messages, new topic, epoch changes and conservative restore revoke authority. Task and memory choices share one durable slot with a domain discriminator; starting another choice can replace the previous choice. Invalid/stale selections cause no mutation. Duplicate updates and recovered committed operations report the persisted change receipt.

## Output and limits

Task summaries show title, Chinese status, local time, timezone and short ID; details show content, catch-up rule and next occurrence. Status/history show execution kind, time, evidence/call counts and delivery problems. Controls use escaped Telegram HTML and read-only navigation; ordinary successful answers remain plain text. Selection buttons carry issued tokens, not arbitrary commands. No button directly toggles settings or deletes an agreement.

Only the authenticated owner's private, direct messages can authorize writes. Forwarded, quoted, negated and hypothetical content cannot authorize task controls; incompatible mixed operations ask for separate requests. Application authorization remains authoritative over model proposals. Pausing a task blocks future starts; stopping an already-running execution requires `/stop ID`. Local usage is not a provider invoice. See [task scheduling](tasks.md) for execution and recovery boundaries.
