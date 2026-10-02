# Model integration, accounting, and safe diagnostics

[简体中文](model-and-accounting.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Sources: [models.py](../../src/kestri/models.py), [runtime.py](../../src/kestri/runtime.py), [budget.py](../../src/kestri/budget.py), [research.py](../../src/kestri/research.py), [smoke.py](../../src/kestri/smoke.py), [redaction.py](../../src/kestri/redaction.py), and [errors.py](../../src/kestri/errors.py). These are implemented adapter/accounting rules, not claims about current provider capacity/prices.

## Model construction and serialization

`build_model()` creates `DeepSeekChatModel` with the configured model/API key, fixed `https://api.deepseek.com/v1`, configured `max_tokens`/timeout, `max_retries=0`, and explicit `extra_body={'thinking': {'type': ...}}`. Ambient SDK base-URL variables do not choose the endpoint. HTTP proxy transport remains a separate environment concern.

`DeepSeekChatModel._get_request_payload()` calls the locked parent serializer, converts the original input to messages, and zips originals with payload messages using `strict=True`. For every original `AIMessage`, a string `additional_kwargs['reasoning_content']` is copied into the outbound assistant message, and `content=None` becomes `''`. Other message fields stay with the parent serializer. Missing/nonstring reasoning is not manufactured.

This isolates a protected SDK hook compensating for the integration's outbound reasoning replay. It is not an alternate reasoning generator or a universal provider abstraction. [Runtime tests](../../tests/test_runtime.py) inspect actual serialized requests in both thinking modes, endpoint selection, tool results, and follow-up. Upgrade the adapter and locked dependency together; do not infer continued compatibility from an import succeeding.

## Minimal session and smoke verification

`AgentSession` builds a separate graph with `checked_add`, model/tool call limits, safe tool errors, `InMemorySaver`, and one UUID thread. `ask()` executes under disabled cloud tracing and an outer timeout, returns immutable `TurnResult(status, answer, messages, elapsed_seconds, error_type)`, and marks a failed/cancelled session unusable for another turn. Cancellation is re-raised; ordinary failed turns read their local snapshot for diagnostic evidence. Only a successful final `AIMessage` supplies the answer.

Statuses are `completed`, `timeout`, `model_limit`, `tool_limit`, `provider_error`, and `internal_error`. These are smoke/session statuses, distinct from persisted product run states. `aclose()` closes model sync/async root clients when supported. Process-local state is not the product's durable archive, budget ledger, memory system, or recovery mechanism.

`run_smoke()` asks addition 17+25, then 8+previous result. `verify_turn()` considers only messages added since the previous turn and requires completed status, an AI tool call, a successful tool result equal to 42 or 50, and that number as a bounded numeric occurrence in the answer. It does not prove every surrounding word is correct or require an answer consisting solely of that number. Failure stops the second turn; model clients close in `finally`.

`turn_evidence()` records status/time/error type, redacted answer, model-response count, tool names/arguments/results, usage metadata, and reasoning-presence booleans. It excludes reasoning text. `run_smoke()` adds schema version 1, kind `deepseek-live-smoke`, UTC time, Python/dependency versions, model/mode/limits, and overall pass. `save_evidence()` writes `smoke-<UUID hex>.json` exclusively with mode 0600 and final whole-document configured-key replacement. New directories request 0700; existing directory permissions are not tightened. Unlike managed research `Workspace`, this operator-selected writer is not an identifier-scoped no-follow directory-handle API.

## Activity and input admission

`RunControl` owns a process-local cancellation event plus durable run ID. `ensure_active()` rejects a signalled or missing/cancelled run, then compares foreground/background run epoch with its conversation epoch. Memory/task control runs are not rejected solely because their own mutation changes the epoch. These checks occur before model/tools/billable reservations and again at business completion where applicable.

`conservative_input_size()` serializes full message `model_dump()` data and tool names/descriptions/JSON schemas with UTF-8, then adds 2048. It includes reasoning and metadata when present. The estimate is intentionally conservative, not exact tokenization. `BoundsMiddleware` counts the actual request including system message before reserving ordinary model work. Summary admission is a separate call using the same utility; selected memory can affect ordinary request size. See [context management](context-management.md).

## Cost units and formulas

`micro_usd(Decimal)` converts USD to integer millionths and rounds upward with `ROUND_CEILING`. `Budget.model_cost()` computes:

```text
estimated micro-USD = ceil(
    input_units × configured input USD per million
    + output_tokens × configured output USD per million
)
```

Example with repository rates: 10,000 estimated input units and maximum 4096 output tokens reserve `ceil(10000×0.30 + 4096×1.20) = 7916` micro-USD, or USD 0.007916. If actual metadata later reports 1000 input and 100 output tokens, the recorded amount becomes 420 micro-USD. This is arithmetic at configured rates, not a provider invoice; cache/discount pricing is not modeled.

Search/extraction each reserve `ceil(search_credit_usd × 1,000,000)`; the default is 8000 micro-USD. A supported basic extraction batch has at most three URLs. Reported credits are metadata; the configured dollar estimate remains unchanged.

## Reservation and settlement transaction

`Budget.reserve()` first checks active work, then passes run/month dollar limits converted to micro-USD to `Store.reserve()`. Under the transaction advisory lock `kestri-budget`, the store requires a running, uncancelled run, sums this UTC month's usage by `created_at` and the run's cumulative usage, checks totals plus proposed amount, and inserts a UUID `reserved` row. Concurrent foreground/background requests cannot both consume the same available local allowance through this transaction path.

All ledger states count toward sums. Month membership is reservation creation time, not provider settlement time; an operation spanning midnight/month-end keeps its row timestamp. A background retry shares its run sum. Controls and summaries with model calls use the ledger too; deterministic memory commands and evidence reads have no external reservation.

| State | Meaning and transition |
| --- | --- |
| `reserved` | Operation admitted before external request |
| `recorded` | Response usage/metadata settled; known model usage can replace amount |
| `unknown` | Run finishes/restarts without known settlement; reserved amount remains |

`settle()` records redacted metadata and optionally replaces the amount; absent amount leaves it unchanged. It does not recheck the configured cap after actual usage replaces an estimate. Failed external calls are not assumed free. This protects local estimated admission, not an absolute provider spending guarantee. There is no reservation refund command or provider billing reconciliation API.

Ordinary model settlement sums available usage from returned AI messages; missing usage preserves estimated amount. Summary settlement uses its response metadata. Run completion marks remaining reservations unknown; process recovery also does so globally. `/usage` counts ledger operations and all amounts created in the UTC month; it is not the number of conversation messages, tool calls, or successful HTTP requests.

## Error taxonomy and visibility

| Error / category | Where used | Observable behavior |
| --- | --- | --- |
| `PolicyDenied` | Authorization, URL/path/UUID, epoch, restore/maintenance | Safe denial classification; tools may return bounded failure data, run may stop |
| `BudgetExceeded` | Transactional estimated spending admission | Terminal budget notice; no automatic retry |
| `ContextExceeded` | Input or summary bounds | Terminal context notice; no fabricated summary |
| `ProviderFailure` | Malformed/oversized provider or missing-answer contracts | Safe provider failure; no raw response body |
| `DeliveryProblem(kind, uncertain, delay)` | Telegram adapter | Separate send classification; see execution/delivery |
| Timeout/call-limit/SDK exceptions | Agent and transport | Safe type-based notice/status, restricted background retry allowlist |

Research selects notices by exception class; unknown exceptions receive a generic failure. Ordinary model SDK errors get a provider-request notice. `safe_research_tool_error()` converts only recognized policy/provider/value/HTTP errors to a bounded failure string; `safe_tool_error()` handles only smoke `ValueError`. The model may correct an input within remaining allowance, but an error message is not proof of success or added permission.

## Redaction and observability boundaries

`Redactor.text()` replaces each configured nonempty secret's exact string with `[REDACTED]`; `data()` serializes JSON, replaces strings, and parses it back. It is exact-value redaction, not a complete classifier, encryption, or a guarantee that encoded/transformed secrets are removed. Research startup registers model/bot/search/DSN secrets; operator data startup registers the DSN. Memory insertion also has a conservative credential-pattern rejection.

Research, task planning, summary calls within research, and smoke disable LangSmith tracing. Business events include `context_compressed`, `tool_rejected_or_failed`, `url_rejected`, and `schedule_decision`; they store redacted structured metadata, not full cloud traces. Maintenance stores its latest report/error class in `meta`; CLI output suppresses raw exceptions. `/status` and `data status` are observational views, not active provider health probes.

Checkpoints may contain raw dialogue, tool material, and provider reasoning despite tracing being disabled. Logical backup excludes graph tables; local checkpoint storage remains private until reset/retention. Smoke evidence has its own restricted schema. Keep these artifacts and proof categories distinct; sanitized evidence does not make every local state public-safe.

## Verification and maintenance

[Runtime tests](../../tests/test_runtime.py) exercise model payloads and failed-session behavior; [evidence tests](../../tests/test_evidence.py) cover absence of reasoning/key text and required tool proof; [research integration tests](../../tests/test_research_integration.py) cover concurrent reservations, spending rejection, unresolved usage, and terminal outcomes. These verify configured arithmetic/control, not provider invoices. For SDK/model changes, review serialized payload, thinking mode, usage metadata, context estimates, timeout/retry behavior, and protected middleware hooks together.
