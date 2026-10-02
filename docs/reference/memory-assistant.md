# Conversational memory operations

[简体中文](memory-assistant.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Natural controls share services with commands.

## Everyday use

Say “帮我开启自动记忆和语义检索”, “回答时先不要使用我的记忆”, “你现在记住了我哪些事情”, “最近记住了什么” or “查看待确认记忆”. Explicit requests execute directly; vague settings need clarification. Learning, answer use and semantic recall are independent. Auto sends future direct chats to DeepSeek; semantic sends eligible facts/history and queries to Beijing DashScope under existing consent and budgets.

Identify the fact to save, correct or forget. Ambiguous targets show at most five choices. Reply “第二条” or click within ten minutes. Choices survive process restart but expire on settings/epoch changes, target revision changes or timeout; consumption is single-use. Ordinary conversation does not select a target.

## Reading and navigation

Home separates settings, counts and recent facts. Read-only buttons open lists, candidates, changes and settings. Lists contain five entries per page; details show readable origin, owner-local time and archive source. `/memory list`, `/memory pending`, `/memory changes`, `/memory settings` and `/memory inspect ID` remain available. Send commands separately. Control receipts use escaped HTML; ordinary answers stay plain text. Buttons accept only the configured owner's private chat.

## Answer evidence

Ask “为什么刚才这样回答” or click “记忆依据”. `/memory why [run ID]` shows actual memory IDs/revisions supplied to successful model calls, retrieval method/fallback and separately observed history search/read IDs. This does not expose reasoning or establish causality. Old answers without records are unavailable. Viewing rechecks consent, epoch, revision, scope, source and lifetime; revoked facts are not displayed. Read-only views and diagnostics make no provider call.

## Implementation and recovery

`management.py` gates current direct-owner requests and makes at most one bounded structured proposal for nontrivial controls. Application validation and shared transactional services perform writes; models have no shell, arbitrary configuration or SQL tool. Read navigation uses deterministic paths. Presentation metadata stores buttons/epoch without copied bodies; diagnostic events store identifiers without facts or queries.

Migration 10 adds `conversations.memory_choice` and `outbox.presentation`. Logical backup schema 8 accepts older schemas 4–7; restore clears choices, presentation and injection/history diagnostic events while retaining quarantine/consent rules. Vectors remain rebuildable. Upgrade with both Compose files and retain pre-migration private snapshots.

See the [design](../design/memory-assistant.md). Telegram transport follows the official [Bot API](https://core.telegram.org/bots/api).
