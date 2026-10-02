# Personal memory and conversation context

[简体中文](memory-and-context.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Scope: M3 implementation; see the [validation record](../development/m3-validation.md).

For the source-level execution path, see [context management](../design/context-management.md); for fields and relations, see [database structure](database.md). This reference remains the command/settings contract.

## Owner controls

All commands appear in the native collapsible Telegram menu. Memory controls are deterministic application operations, without model calls. Only direct authorized owner messages can write memory; forwarded commands, research results, inference, and summaries cannot. A suggested preference requires a new explicit save instruction.

| Input | Behavior |
| --- | --- |
| `/remember CONTENT` or `记住：CONTENT` | Save exactly that content as global memory |
| `/remember task TASK_ID CONTENT` | Save memory only for that task; require an unambiguous 8+ character UUID prefix |
| `/remember expires=2099-01-01T00:00:00+00:00 CONTENT` | Explicit future, timezone-aware ISO expiry; may precede `task TASK_ID CONTENT` |
| `/memory` | Inspect active, unexpired entries, IDs, scope, source Telegram message, timestamps, and expiry |
| `/correct MEMORY_ID CONTENT` or `更正记忆 MEMORY_ID CONTENT` | Supersede the active entry with new exact content, preserving task scope and expiry |
| `/forget MEMORY_ID` or `忘记记忆 MEMORY_ID` | Tombstone one active entry and invalidate automatic context |
| `/history` | Read the latest ten original archive records with IDs and bounded previews |
| `/history RECORD_ID [OFFSET]` | Read that owner's original record in 3000-character pages; display continuation when needed |

An unambiguous active memory ID is required for correction/forgetting; no bulk delete or semantic target guessing. Save bodies are limited to 1200 characters. Credential-labelled content, recognizable key formats, and configured-secret redactions are rejected; this is a conservative filter, not a complete sensitive-data classifier. Do not store credentials as memory. Explicit remembering is retention intent; the app does not automatically infer personal facts.

## Persistence and retrieval

Migration 3 stores content, source message/run, global/task scope, creation/update time, supersession, expiry, and active/superseded/forgotten/expired status. Run-keyed change acknowledgements commit with mutations; duplicate updates and restart after commit do not reapply changes. Canonical messages, tasks, source evidence, checkpoints, and memories remain separate.

Structured owner/scope/expiry filtering precedes bounded retrieval. Task memories precede global entries, keyword matches rank within scope, and recency breaks ties. No vectors or automatic archive extraction are used. Selected memories are inserted only in the current model request, labelled as data; they are not written into graph message state or summaries. Model answers can mention them, so invalidation also covers the dialogue containing such answers.

Every successful save/correction/forget operation clears the foreground checkpoint pointer and increments an owner context epoch. Expiry does the same before new work/model access. Old foreground/background results and evidence from another epoch are excluded from automatic reply/read retrieval, and stale running work cannot start another billable operation or restore the old foreground head. An already-submitted external request cannot be recalled; if it completes after the epoch changes, its answer is replaced by a safe stopped-context notice instead of being delivered. This intentionally broad invalidation sacrifices conversation continuity to avoid deleted-fact resurrection. `/history` is an explicit, read-only archive view and does not feed the model or create memory.

Forgotten content remains in tombstoned rows, archives, and historical checkpoints until the M4 [retention/deletion policy](data-lifecycle.md) removes local copies. Provider/Telegram copies remain outside that boundary. Restore quarantines imported active facts; use a new explicit save to authorize an intended fact.

## Automatic compression

The locked LangChain `SummarizationMiddleware` chooses a safe cutoff preserving recent complete tool calls/results. Kestri extends its summary call to enforce active-run checks, input admission, output size, a separate call cap, local spending reservation/settlement, and the enclosing run timeout. Regression tests cover this small protected-method extension; review it when upgrading LangChain.

At the trigger, summarize an older prefix and keep recent messages in the graph checkpoint. Original messages remain in the PostgreSQL archive. The prompt preserves goals, decisions, explicit corrections, constraints, unresolved questions, and evidence references, keeping source claims and model inference distinct. The summary is a historical data message, never permission, a task agreement, or personal memory. Main and background contexts remain separate.

Full summary input must fit the admission limit; older data is not silently clipped. Empty/oversized summaries, provider failures, budget exhaustion, excessive compression, or a recent tool block that still cannot fit terminate with a safe notice. No fabricated fallback summary or unbounded retry is used. `/new` starts fresh foreground context while preserving memory, tasks, and archives. Summary quality is model-dependent; retained originals allow explicit inspection.

## Settings and limits

| Variable | Default | Range / meaning |
| --- | --- | --- |
| `KESTRI_MEMORY_LIMIT` | 64 | 1–64 active entries |
| `KESTRI_MEMORY_CONTEXT_LIMIT` | 8 | 1–16 entries per request |
| `KESTRI_CONTEXT_TRIGGER_RATIO` | 0.70 | 0.1–0.9 of the existing input budget; includes prompt/tool and selected-memory overhead estimate |
| `KESTRI_CONTEXT_KEEP_MESSAGES` | 12 | 4–40 recent messages; safe tool-boundary retention may keep more |
| `KESTRI_MAX_SUMMARY_CALLS` | 2 | 1–4 summary calls per run, separate from regular agent model-call count |
| `KESTRI_SUMMARY_MAX_CHARS` | 4000 | 500–8000 summary characters |

Summary calls share per-run/monthly spending limits and the selected DeepSeek model/output limit. The estimate is conservative UTF-8/framing accounting, not the exact provider tokenizer. Final model admission checks the assembled request, including injected memory and schemas. M4 supplies physical retention and quarantined backup recovery; see the [data reference](data-lifecycle.md).
