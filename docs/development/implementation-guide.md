# Implementation reading map and maintenance contracts

[简体中文](implementation-guide.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Scope: all 26 Python source modules, module/class callable entry points, SQL, tests, and engineering configuration. Source governs behavior; internal symbols are not a promised stable public API.

## How to read

Begin with [CLI](../reference/cli.md) and [architecture](../design/architecture.md). Follow [execution/delivery](../design/execution-and-delivery.md), [task scheduling](../design/task-scheduling.md), [context](../design/context-management.md), [tools](../design/tools.md), [model/accounting](../design/model-and-accounting.md), [data maintenance](../design/data-maintenance.md), or [database](../reference/database.md) for a specific question. Entries below identify symbol responsibilities; linked guides own their detailed algorithms and constraints.

## __init__.py

[Source](../../src/kestri/__init__.py)

Package description and `__version__ = "0.1.0"` only; release changes must keep the project version in `pyproject.toml` aligned. Importing this file does not start the application.

## application.py

[Source](../../src/kestri/application.py)

Application coordination · [Detailed mechanism](../design/execution-and-delivery.md)

| Symbol | Responsibility |
| --- | --- |
| `Application.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `Application.accept_update` | Authorize/route input, durably accept it, and wake/cancel workers. |
| `Application.polling` | Poll with durable offset; classify delays; advance after handling. |
| `Application.work_once` | Expire memory, claim a run, track/cancel its task, finalize unexpected failures. |
| `Application.working` | Repeatedly execute one worker lane and wait/recheck while idle. |
| `Application.scheduling` | Tick stored agreements, wake run workers, wait the configured interval. |
| `Application.deliver_once` | Claim one saved send and record success or classified failure. |
| `Application.delivering` | Drain pending ordered sends with wakeup/recheck and rate spacing. |
| `Application.prepare_restore` | Consume the one-time stale-update discard marker and queue a notice. |
| `Application.serve` | Prepare/recover, then supervise six concurrent loops. |
| `run_telegram` | Create resources, verify webhook/identity/lease, configure menu, close clients. |
| `show_telegram_ids` | Inspect private pending senders without enrolling or model work. |

## budget.py

[Source](../../src/kestri/budget.py)

Control and accounting · [Detailed mechanism](../design/model-and-accounting.md)

| Symbol | Responsibility |
| --- | --- |
| `micro_usd` | Convert Decimal USD upward to integer millionths. |
| `RunControl.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `RunControl.ensure_active` | Check local/durable cancellation and research epoch freshness. |
| `Budget.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `Budget.model_cost` | Round configured input/output rate arithmetic upward. |
| `Budget.reserve` | Check activity, convert limits, request atomic ledger reservation. |
| `Budget.provider_usage` | Settle provider metadata without changing the reserved amount. |
| `conservative_input_size` | Serialize complete messages/tool schemas; count UTF-8 bytes plus framing. |

## cli.py

[Source](../../src/kestri/cli.py)

CLI routing · [Detailed mechanism](../reference/cli.md)

| Symbol | Responsibility |
| --- | --- |
| `run_data` | Select operator action; initialize storage/workspace; print JSON; close pool. |
| `main` | Build argument tree, choose settings, execute command, classify exit/error output. |

## context.py

[Source](../../src/kestri/context.py)

Request context middleware · [Detailed mechanism](../design/context-management.md)

| Symbol | Responsibility |
| --- | --- |
| `ContextSummary.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `ContextSummary._acreate_summary` | Validate/admit/reserve/invoke/settle a bounded historical summary. |
| `ContextSummary._build_new_messages` | Frame summary as untrusted historical HumanMessage. |
| `MemoryContext.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `MemoryContext.awrap_model_call` | Expire/check epoch, retrieve facts, temporarily override system message. |

## data.py

[Source](../../src/kestri/data.py)

Operator data lifecycle · [Detailed mechanism](../design/data-maintenance.md)

| Symbol | Responsibility |
| --- | --- |
| `disk_operation` | Shield file worker and wait before propagating cancellation. |
| `encoded` | Canonical sorted-key UTF-8 JSON with string fallback. |
| `write_private` | Bounded exclusive no-follow private write, fsync and partial cleanup. |
| `read_private` | Validate file permissions/type/size, envelope, checksum, format. |
| `DataService.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `DataService.exclusive` | Acquire data/bot leases, verify owner, lock conversations. |
| `DataService.status` | Count business records and read latest maintenance metadata. |
| `DataService.backup` | Stream bounded business rows and optional evidence to a private bundle. |
| `DataService.restore` | Validate empty target, transform authority, import/files/sequences, roll back failures. |
| `DataService.cleanup` | Preview/defer/revoke content; commit metadata before physical cleanup. |
| `DataService.prune_backups` | Remove only recognized old managed backup bundles. |
| `DataService.maintaining` | Periodically clean and retain safe latest outcomes/errors. |

## embedding.py

[Source](../../src/kestri/embedding.py) · [Interface/configuration](../reference/embedding.md)

`EmbeddingBatch` holds validated immutable vectors/usage; `EmbeddingClient.__init__` captures settings/HTTP client, and `embed` performs bounded requests and validation; `cosine_similarity` supports the fixed comparison; `run_embedding_smoke` sends only non-private test texts; `save_embedding_evidence` writes sanitized JSON. `EmbeddingSettings` validates key, numeric dimensions and Beijing endpoint. Product automatic memory is specified in [Memory v2](../design/memory-v2.md), not implemented.

## errors.py

[Source](../../src/kestri/errors.py)

Failure categories · [Detailed mechanism](../design/model-and-accounting.md)

| Symbol | Responsibility |
| --- | --- |
| `PolicyDenied` | Authorization/policy error category without private payload. |
| `BudgetExceeded` | Estimated-spend rejection category. |
| `ContextExceeded` | Context/summary admission rejection category. |
| `ProviderFailure` | Provider/response contract failure category. |

## http.py

[Source](../../src/kestri/http.py)

Bounded HTTP · [Detailed mechanism](../design/tools.md)

| Symbol | Responsibility |
| --- | --- |
| `post_json` | Stream bounded JSON; validate HTTP/envelope; return a dictionary or safe failure. |

## memory.py

[Source](../../src/kestri/memory.py)

Explicit memory service · [Detailed mechanism](../design/context-management.md)

| Symbol | Responsibility |
| --- | --- |
| `memory_instruction` | Recognize slash/natural explicit memory command and body. |
| `display` | Format memory scope/status/provenance/time/expiry and quarantine warning. |
| `listing` | Read up to 64 active/quarantined unexpired records without a model. |
| `MemoryService.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `MemoryService.apply` | Validate active direct command; mutate exact fact/target; commit acknowledgement/epoch. |
| `MemoryService._insert` | Reject credential patterns, enforce active-record limit, insert provenance/supersession. |
| `MemoryService.expire` | Tombstone due active facts and invalidate conversation epoch/head. |
| `MemoryService.retrieve` | Filter owner/status/expiry/task, then rank keywords/scope and bound selection. |

## models.py

[Source](../../src/kestri/models.py)

Provider serialization adapter · [Detailed mechanism](../design/model-and-accounting.md)

| Symbol | Responsibility |
| --- | --- |
| `DeepSeekChatModel._get_request_payload` | Delegate serialization, replay string reasoning, normalize null assistant content. |

## redaction.py

[Source](../../src/kestri/redaction.py)

Configured-secret redaction · [Detailed mechanism](../design/model-and-accounting.md)

| Symbol | Responsibility |
| --- | --- |
| `Redactor.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `Redactor.text` | Replace exact nonempty configured values with a marker. |
| `Redactor.data` | JSON-serialize, redact, parse structured metadata. |

## research.py

[Source](../../src/kestri/research.py)

Product agent execution · [Detailed mechanism](../design/architecture.md)

| Symbol | Responsibility |
| --- | --- |
| `BoundsMiddleware.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `BoundsMiddleware.awrap_model_call` | Check activity and full input, reserve model spend, settle returned usage. |
| `BoundsMiddleware.awrap_tool_call` | Check activity and record selected tool failure categories. |
| `safe_research_tool_error` | Return bounded recognized tool failure data, never raw exception text. |
| `ResearchAgent.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `ResearchAgent.run` | Route controls or build bounded research graph, seed context, produce source footer, finish. |

## runtime.py

[Source](../../src/kestri/runtime.py)

Minimal model integration session · [Detailed mechanism](../design/model-and-accounting.md)

| Symbol | Responsibility |
| --- | --- |
| `TurnResult` | Immutable status/answer/messages/time/error result; see model/session contract. |
| `build_model` | Fix official endpoint/mode, output/timeout and zero SDK retries. |
| `safe_tool_error` | Convert smoke range errors to a safe failure string. |
| `AgentSession.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `AgentSession.ask` | Execute one in-memory turn, classify result, reject reuse after failure/cancellation. |
| `AgentSession.aclose` | Close supported synchronous/asynchronous model HTTP clients. |

## schedule.py

[Source](../../src/kestri/schedule.py)

Wall-clock algorithms · [Detailed mechanism](../design/task-scheduling.md)

| Symbol | Responsibility |
| --- | --- |
| `occurrence` | Round-trip local time/UTC; skip DST gap, choose earlier fold. |
| `next_occurrence` | Scan 15 days forward for a strictly future matching weekday. |
| `latest_occurrence` | Scan 15 days backward for latest due matching weekday. |
| `requested_time` | Parse explicit numeric/Chinese time and validate hour/minute. |
| `requested_weekdays` | Recognize weekdays/daily/explicit day names and sort unique values. |

## settings.py

[Source](../../src/kestri/settings.py)

Validated configuration models · [Detailed mechanism](../reference/cli.md)

| Symbol | Responsibility |
| --- | --- |
| `Settings` | Minimal session settings; required model key and per-turn limits. |
| `Settings.require_nonempty_key` | Reject a blank model key without returning it in validation output. |
| `TelegramCredentials` | Onboarding-only bot-token settings. |
| `TelegramCredentials.validate_token` | Validate full Bot API token pattern. |
| `DataSettings` | Operator DSN/owner/workspace/retention; optional DashScope key for redaction. |
| `ResearchSettings` | Combined runtime/data/product fields, complete catalog in CLI reference. |
| `ResearchSettings.validate_timezone` | Validate optional IANA owner timezone with ZoneInfo. |
| `ResearchSettings.require_token` | Reuse Telegram token validator for product settings. |
| `ResearchSettings.require_secret` | Reject blank search key/DSN for product startup. |

## smoke.py

[Source](../../src/kestri/smoke.py)

Live smoke and evidence · [Detailed mechanism](../design/model-and-accounting.md)

| Symbol | Responsibility |
| --- | --- |
| `verify_turn` | Require new successful expected tool result plus completed numeric answer. |
| `turn_evidence` | Extract observable tool/usage data and reasoning-presence flags. |
| `run_smoke` | Run 42 then 50 workflow, stop on verification failure, close session. |
| `save_evidence` | Exclusively save schema evidence with key redaction and private mode. |

## store.py

[Source](../../src/kestri/store.py)

Business transactions · [Detailed mechanism](../reference/database.md)

| Symbol | Responsibility |
| --- | --- |
| `chunks` | Split at 3500 characters and supply an empty-result placeholder. |
| `Store.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `Store.open` | Open pool and run four idempotent business migrations under a transaction lock. |
| `Store.close` | Close connection pool. |
| `Store.one` | Fetch one dictionary row using parameterized SQL. |
| `Store.all` | Fetch dictionary rows using parameterized SQL. |
| `Store.execute` | Execute a standalone statement with supplied parameters. |
| `Store.bind_identity` | Insert or verify immutable database bot/owner binding. |
| `Store.offset` | Read durable next update ID, default zero. |
| `Store.advance_offset` | Persist monotonic max next update ID. |
| `Store.accept` | Atomically deduplicate, archive, queue/control, and acknowledge input. |
| `Store._command_notice` | Produce deterministic owner status/history/list/reset/help responses. |
| `Store.claim_run` | Invalidate stale background work, claim ready lane and capture source/epoch. |
| `Store.cancelled` | Treat missing run or cancellation flag as cancelled. |
| `Store.finish` | Reconcile controls/cancellation/epoch/retry, terminal spend/head/outbox transaction. |
| `Store.recover` | Finalize interrupted running work/control commits; quarantine sends and reservations. |
| `Store.reply_context` | Resolve owner reply to completed current-epoch nonexpired research result. |
| `Store.add_evidence` | Persist redacted source metadata linked to a run. |
| `Store.event` | Persist a redacted structured operational event. |
| `Store.reserve` | Serialize spend admission and insert micro-USD reservation. |
| `Store.settle` | Record redacted usage and optionally replace reserved amount. |
| `Store.claim_delivery` | Claim earliest ready pending sequence and increment send attempts. |
| `Store.delivered` | Commit successful message ID and outbound archive. |
| `Store.delivery_failed` | Choose retry/failed/uncertain and bound next-attempt delay. |

## task_agent.py

[Source](../../src/kestri/task_agent.py)

Task proposal execution · [Detailed mechanism](../design/task-scheduling.md)

| Symbol | Responsibility |
| --- | --- |
| `TaskAgent.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `TaskAgent.run` | Extract current allowed TaskPlan, apply policy, recover committed acknowledgement. |

## task_intent.py

[Source](../../src/kestri/task_intent.py)

Delegation recognizer · [Detailed mechanism](../design/task-scheduling.md)

| Symbol | Responsibility |
| --- | --- |
| `task_intent` | Conservatively route current direct recurring/control phrases. |

## tasks.py

[Source](../../src/kestri/tasks.py)

Agreement service · [Detailed mechanism](../design/task-scheduling.md)

| Symbol | Responsibility |
| --- | --- |
| `TaskPlan` | Structured proposal fields/validators, not direct authorization. |
| `TaskPlan.valid_days` | Reject duplicate/out-of-range weekday values, return sorted list. |
| `TaskPlan.valid_zone` | Validate optional proposal IANA timezone. |
| `agreement` | Display exact persisted schedule/content/lifecycle and restore warnings. |
| `list_tasks` | List owner nondeleted agreements without model inference. |
| `TaskService.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `TaskService.apply` | Revalidate direct intent/fields/target and commit agreement plus acknowledgement. |
| `TaskService.tick` | Coalesce/skip due work under locks, respect capacity, persist occurrence and decision. |

## telegram.py

[Source](../../src/kestri/telegram.py)

Bot transport and routing · [Detailed mechanism](../design/execution-and-delivery.md)

| Symbol | Responsibility |
| --- | --- |
| `DeliveryProblem.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `TelegramClient.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `TelegramClient.call` | Post bounded API request and classify ok/rejection/rate-limit contracts. |
| `TelegramClient.identity` | Validate getMe result and integer bot ID. |
| `TelegramClient.configure_menu` | Register owner-scoped bilingual commands and menu button. |
| `TelegramClient.poll` | Request message updates with offset, server wait and batch bound. |
| `TelegramClient.send` | Send plain saved text and distinguish known/uncertain outcome. |
| `authorized_message` | Enforce owner, private chat, nonbot, text/message identity. |
| `command_for` | Recognize exact stops and supported slash names/bot suffix. |

## tools.py

[Source](../../src/kestri/tools.py)

Smoke tool · [Detailed mechanism](../design/tools.md)

| Symbol | Responsibility |
| --- | --- |
| `AddInput` | Strict bounded operand schema, unknown fields forbidden. |
| `checked_add` | Validate bounded strict operands and sum; return numeric string. |

## url_policy.py

[Source](../../src/kestri/url_policy.py)

Public target policy · [Detailed mechanism](../design/tools.md)

| Symbol | Responsibility |
| --- | --- |
| `resolve_host` | Bound system DNS and return distinct addresses. |
| `CloudflareResolver.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `CloudflareResolver.__call__` | Fetch bounded A/AAAA DoH records without fallback or service credentials. |
| `PublicURLPolicy.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `PublicURLPolicy.validate` | Reject unsafe URL/address/secret-query forms and strip fragment. |

## web.py

[Source](../../src/kestri/web.py)

Information tool adapters · [Detailed mechanism](../design/tools.md)

| Symbol | Responsibility |
| --- | --- |
| `SearchInput` | Strict query/topic schema; see tool input table. |
| `ExtractInput` | Strict one-to-three URL list schema. |
| `EvidenceInput` | Strict evidence-ID field; UUID policy is enforced during read. |
| `WebTools.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `WebTools.output` | Redact and enforce whole JSON output size. |
| `WebTools.evidence` | Retain bounded text, insert source metadata, return excerpt contract. |
| `WebTools.search` | Reserve fixed search estimate, validate candidates, retain snippets. |
| `WebTools.extract` | Validate/deduplicate URLs, reserve, match exact results and retain failures/pages. |
| `WebTools.read` | Validate evidence UUID/owner/epoch/status and bounded workspace read. |
| `WebTools.tools` | Bind three schema-validated model tool wrappers to this run service. |

## workspace.py

[Source](../../src/kestri/workspace.py)

Scoped evidence filesystem · [Detailed mechanism](../design/tools.md)

| Symbol | Responsibility |
| --- | --- |
| `Workspace.__init__` | Construct/capture component dependencies and local state; see owning guide for defaults/resources. |
| `Workspace.directory` | Open UUID-relative no-follow directory handles; optionally create. |
| `Workspace.write` | Create private evidence file exclusively with no-follow. |
| `Workspace.read` | Read limit+1 characters and report clipping. |
| `Workspace.remove` | Unlink one generated evidence file without following directory links. |

## SQL and engineering files

The four [SQL migrations](../reference/database.md) define business state, cyclic task foreign keys, epochs, and restore fields; the saver owns separate framework tables. The following files also shape implementation:

| File | Contract |
| --- | --- |
| [pyproject.toml](../../pyproject.toml) | Python >=3.14, Hatchling package, entrypoint, dependency ranges, Ruff/mypy/pytest policy. |
| [uv.lock](../../uv.lock) | Locked resolution; `uv sync --locked` is the reproducible dependency path. |
| [.python-version](../../.python-version) | Development interpreter selection. |
| [.env.example](../../.env.example) | Public placeholders/example values, not owner credentials or every supported setting. |
| [compose.yaml](../../compose.yaml) | App/database networks, persistent volumes, supervision, limits, health checks. |
| [compose.dev.yaml](../../compose.dev.yaml) | Explicit loopback database port for host development; weakens base network exposure deliberately. |
| [Dockerfile](../../Dockerfile) | Locked no-dev environment, package/source copy, nonroot entrypoint and workspace. |
| [.gitignore](../../.gitignore) | Exclude secrets/local state/caches/build outputs from ordinary Git tracking. |
| [.dockerignore](../../.dockerignore) | Keep secrets/local state/caches out of build context. |
| [.github/workflows/checks.yml](../../.github/workflows/checks.yml) | Offline/database Linux checks and package build; no provider acceptance or publishing. |
| [scripts/check_docs.py](../../scripts/check_docs.py) | Pairs/language links/local files/heading counts/engineering IDs; no anchors/prose quality check. |

## Test organization and evidence

Tests use real libraries with mock transport; they are not live-service proof. Database cases drop the business schema in disposable `kestri_test`. `conftest.py` captures test DSN before environment isolation, removes specified model/proxy/KESTRI environment values through an autouse fixture, and disables `.env` in settings builders. The lifecycle suite additionally clears checkpoint state and binds test identity. Shared model/DNS/Telegram/scenario builders live in `helpers.py`, not other test modules.

| File | Verification boundary |
| --- | --- |
| [test_settings.py](../../tests/test_settings.py) | Configuration key/mode/range validation. |
| [test_tools.py](../../tests/test_tools.py) | Strict bounded addition. |
| [test_evidence.py](../../tests/test_evidence.py) | Observable tool proof, key/reasoning exclusion, file mode. |
| [test_runtime.py](../../tests/test_runtime.py) | Actual graph/SDK payload, follow-up, limits, cancellation. |
| [test_boundaries.py](../../tests/test_boundaries.py) | Public URL/DNS, workspace, HTTP/Telegram contracts/menu. |
| [test_schedule.py](../../tests/test_schedule.py) | Clock parsing and DST recurrence. |
| [test_research_integration.py](../../tests/test_research_integration.py) | Acceptance, persistence, budgets, sources, workers, delivery/recovery. |
| [test_tasks_integration.py](../../tests/test_tasks_integration.py) | Authorization, agreements, coalescing, retries, controls. |
| [test_memory_context_integration.py](../../tests/test_memory_context_integration.py) | Explicit memory, scope/revocation/expiry, compression. |
| [test_data_lifecycle_integration.py](../../tests/test_data_lifecycle_integration.py) | Private backups, quarantine, retention, failed disk operations/leases. |
| [conftest.py](../../tests/conftest.py) | Environment isolation, noncollectable settings helper, disposable store fixture. |
| [helpers.py](../../tests/helpers.py) | Shared offline transports and owner/task/memory scenario setup. |
| [__init__.py](../../tests/__init__.py) | Empty package marker enabling relative helper imports. |

Commands are in [run checks](../how-to/run-checks.md). Historical M0–M4 records retain their acceptance identity. New behavior needs new evidence; controlled tests, remote CI, live APIs, deployment, and long-term use remain separate claims.

## Documentation coverage and change ownership

Coverage is traceable implementation documentation, not a formal correctness proof or stable SDK promise. New modules/methods update this map; fields/migrations update database and backup format; routing/states update execution/task guides; tools update schemas/side effects/evidence; settings update CLI; compression/memory update context. Update both languages. References own numeric contracts, design guides explain algorithms, and historical evidence preserves its original scope.
