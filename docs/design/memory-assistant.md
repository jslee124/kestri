# Conversational memory management

[简体中文](memory-assistant.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Status: approved implementation scope; runtime evidence will be recorded separately.

## Interaction contract

Natural-language management, slash commands and owner-only buttons use the same memory services. Support viewing memory/settings, changes, candidates, detail and actual answer diagnostics; explicit automatic/use/semantic settings; save/correct/forget; multiple independent setting changes. A direct, unambiguous request executes without redundant confirmation. Ambiguous settings or targets ask a focused question. Quoted, conditional, forwarded, external and historical instructions cannot authorize a write. An issued short-lived target choice binds the action, replacement content and target revisions; numbered replies and buttons revalidate that choice. No arbitrary commands, configuration keys, credentials, budgets or database access are exposed to the model.

A bounded structured model proposal interprets only the current direct owner request. The application validates allowed actions and current authority, commits controls, and produces the authoritative receipt. State-changing management completes outside the ordinary research graph so epoch/context resets cannot invalidate its own receipt. Model output is never proof that a setting changed. Read-only navigation may use deterministic fast paths. Mixed unrelated requests and underspecified writes clarify rather than silently discard text.

## Presentation

Memory home shows separate automatic recording, answer use and semantic retrieval states, eligible memory/candidate counts and short recent records. Read-only buttons navigate pages, candidates, changes and settings. Details prioritize content, scope, local time and source; technical metadata stays in inspect/diagnostics. Lists are bounded and paginated. Empty changes have one sentence; pending/failed maintenance adds useful status, not repeated empty categories. User-controlled text is escaped before Telegram HTML. Generated control replies use typed presentation; ordinary model answers remain plain text. Multiple slash commands in one message explain separate sends and make no changes.

## Actual diagnostics

Record each actual model-call memory injection as IDs/revisions and profile/related categories, retrieval method and fallback, with no copied query or fact body. Record actual issued history-search candidates and full reads separately. `/memory why [run ID]` shows what was supplied, not claims about private reasoning or causality. Only completed owner foreground answers are selectable; old answers without records say unavailable. Inspection rechecks current consent, epoch, revisions, scope, source existence and eligibility, so revoked/deleted/expired data is not redisplayed. Use existing event retention; logical restore discards diagnostic/choice state. Reading diagnostics requires no provider request.

## Delivery and acceptance

Document first, then shared presentation, conversational control/selection, diagnostics and owner-only callbacks. Verify meaningful parsing, proposal authority, duplicate/restart recovery, settings reset receipts, ambiguity/stale/expired choices, callback ownership, HTML escaping/bounds, diagnostics after correction/forget/cleanup/restore and actual framework integration. Run both plain PostgreSQL and pgvector checks, type/style/docs/SQL/package checks. Real Telegram acceptance uses an isolated synthetic database and workspace; production poll offset is reconciled before final deployment. Back up production, deploy, restart, verify actual UI and exact-source CI, and retain bilingual completion evidence.

[Completion evidence](../development/memory-assistant-completion.md).
