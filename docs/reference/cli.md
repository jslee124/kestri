# CLI and complete configuration

[简体中文](cli.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Scope: [cli.py](../../src/kestri/cli.py), every field in [settings.py](../../src/kestri/settings.py), and application-owned fixed limits. Values describe this source revision, not current provider pricing.

## Entry point and commands

The installed entry point is `kestri = kestri.cli:main`. `uv run kestri ...` uses the project environment; the container entrypoint already supplies `kestri`, so Compose arguments start with `telegram` or `data`. With no subcommand, argparse prints usage and exits 2. `--help` exits 0 without constructing settings or contacting providers.

| Command | Settings class | Behavior / arguments |
| --- | --- | --- |
| `smoke` | `Settings` | Two bounded live model/tool turns; writes evidence; no flags for arbitrary prompts |
| `embedding-smoke` | `EmbeddingSettings` | One request, three fixed texts; no database/archive access; sanitized JSON evidence |
| `telegram` | `ResearchSettings` | Long-running owner bot; model, search, database, scheduling, and retention |
| `telegram-id` | `TelegramCredentials` | Read bot identity and pending private sender IDs; does not enroll an owner or start model work |
| `data status` | `DataSettings` | Open pool without migrations; report table counts and maintenance metadata |
| `data backup [path]` | `DataSettings` | Create logical private bundle; path optional |
| `data export path` | `DataSettings` | Business-record JSON without evidence text; path required; not restorable |
| `data restore path [--apply]` | `DataSettings` | Validate empty-target restore by default; apply explicitly |
| `data cleanup [--apply]` | `DataSettings` | Preview retention or apply it |
| `data delete-history [--before ISO] [--apply]` | `DataSettings` | Default cutoff is current UTC time; optional ISO timestamp must be timezone-aware |
| `data erase [--apply]` | `DataSettings` | Preview/apply content erasure; not a database wipe |

All `data` commands except `status` call `Store.open()` before the operation, so migration setup can occur even when the operation defaults to a preview. CLI initialization also constructs `Workspace`, which can create the configured root. “Dry run” means no requested import/content deletion, not zero setup side effects. `status` needs an existing initialized schema; it is not a bootstrap command.

## Configuration loading and validation

Settings constructors read process environment, then `.env` in the current working directory, then defaults. Names are case-insensitive; unknown `.env` keys are ignored. The supported classes are not strict tool-input schemas: Pydantic parses numeric environment strings into their declared types. Relative paths resolve from the process working directory. The program has no global config file search, dynamic reload, or remote configuration service.

Most variables use `KESTRI_`. Credentials/DSN use explicit aliases below. `TelegramCredentials` reads only the bot token; `DataSettings` needs no provider keys. `ResearchSettings` inherits both runtime and data fields and overrides the runtime limits for product work. [.env.example](../../.env.example) explicitly sets product-sized limits, so copying it can change smoke limits too. Missing means absent: an empty numeric/timezone value is not equivalent to omitting it.

### Credentials and storage

| Variable | Default / validation | Used by |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | Required nonblank `SecretStr`; runtime validator checks stripped content but returns original value | Smoke, bot |
| `TELEGRAM_BOT_TOKEN` | Required; full match `[0-9]+:[A-Za-z0-9_-]{20,}` | ID discovery, bot |
| `TAVILY_API_KEY` | Required nonblank `SecretStr` | Bot |
| `DATABASE_URL` | Required; nonblank checked for bot; `DataSettings` declares required `SecretStr` without that extra nonblank validator; actual connection validates usability | Bot, data |
| `KESTRI_TELEGRAM_OWNER_ID` | Required integer >0 | Bot, data |
| `KESTRI_WORKSPACE_DIR` | `.kestri/workspace`; path, application rejects symlink root; Compose explicitly uses `/workspace` | Bot, data |
| `KESTRI_EVIDENCE_DIR` | `.kestri/evidence`; path for smoke JSON; not research page storage | Smoke; inherited by bot but unused for bot evidence |

`POSTGRES_PASSWORD` is a Compose interpolation input, not a Python settings field. Compose builds `DATABASE_URL` for the `postgres` service; use a suitable URL-safe value or encode it correctly in a DSN. Secrets are hidden from settings repr/validation output, but this is not encryption of `.env`, database rows, or files.

### Model and execution

| Variable | Smoke default | Bot default | Validation / meaning |
| --- | --- | --- | --- |
| `KESTRI_MODEL` | `deepseek-flash` | Same | String length 1–100; alternate model behavior requires validation |
| `KESTRI_THINKING_MODE` | `disabled` | Same | `disabled` or `enabled`; provider request override |
| `KESTRI_MAX_MODEL_CALLS` | 4 | 8 | Integer 1–20; regular model calls per turn/run |
| `KESTRI_MAX_TOOL_CALLS` | 4 | 8 | Integer 1–20; tool calls per turn/run |
| `KESTRI_RUN_TIMEOUT_SECONDS` | 60 | 120 | >0, ≤300; outer execution deadline |
| `KESTRI_REQUEST_TIMEOUT_SECONDS` | 20 | 30 | >0, ≤120; DeepSeek/Tavily HTTP setting |
| `KESTRI_MAX_OUTPUT_TOKENS` | 1024 | 4096 | Integer 64–8192; output limit per model request |

Task proposal extraction has a fixed two-model-call cap. Summary calls use the separate setting below. Telegram HTTP timeout is fixed at 40 seconds, long poll wait at 25 seconds, DNS client at 5 seconds; changing the provider timeout does not change those.

### Research admission and spending

| Variable | Bot default | Validation / meaning |
| --- | --- | --- |
| `KESTRI_INPUT_TOKEN_BUDGET` | 128000 | Integer 4096–256000; UTF-8/framing admission heuristic, not exact provider tokens |
| `KESTRI_TOOL_OUTPUT_CHARS` | 12000 | Integer 2000–32000; whole serialized tool result |
| `KESTRI_MAX_REPLY_CHARS` | 12000 | Integer 1000–16000; target body limit; truncation notices may extend it |
| `KESTRI_URL_DNS_MODE` | `system` | `system` or `cloudflare`; no failure fallback |
| `KESTRI_QUEUE_LIMIT` | 8 | Integer 1–32; queued/running non-background requests, including task/memory controls |
| `KESTRI_MONTHLY_BUDGET_USD` | 20 | Decimal >0, ≤1000; local UTC-month envelope |
| `KESTRI_RUN_BUDGET_USD` | 0.50 | Decimal >0, ≤20; one run, including background retry |
| `KESTRI_INPUT_USD_PER_MILLION` | 0.30 | Decimal >0, ≤100; configured input estimation rate |
| `KESTRI_OUTPUT_USD_PER_MILLION` | 1.20 | Decimal >0, ≤100; configured output estimation rate |
| `KESTRI_SEARCH_CREDIT_USD` | 0.008 | Decimal >0, ≤1; reservation estimate for each search/extraction batch |

Rates are application estimates. There is no automatic price refresh, prepaid-credit fetch, provider-side cap, or unknown-request refund. Standard HTTP proxy variables are inherited by HTTPX clients; their reachability differs between host and container. They are transport environment, not settings fields. `DEEPSEEK_API_BASE` cannot replace the fixed model endpoint.

### Memory and compression

| Variable | Bot default | Validation / meaning |
| --- | --- | --- |
| `KESTRI_MEMORY_LIMIT` | 64 | Integer 1–64 active explicit records |
| `KESTRI_MEMORY_CONTEXT_LIMIT` | 8 | Integer 1–16 selected records per request |
| `KESTRI_CONTEXT_TRIGGER_RATIO` | 0.70 | 0.1–0.9 of local input threshold |
| `KESTRI_CONTEXT_KEEP_MESSAGES` | 12 | Integer 4–40; tool boundaries can change actual retention |
| `KESTRI_MAX_SUMMARY_CALLS` | 2 | Integer 1–4 per run |
| `KESTRI_SUMMARY_MAX_CHARS` | 4000 | Integer 500–8000; validated summary output |

### Recurring tasks

| Variable | Bot default | Validation / meaning |
| --- | --- | --- |
| `KESTRI_OWNER_TIMEZONE` | Unset (`None`) | If present, `ZoneInfo` must recognize it; no implicit timezone |
| `KESTRI_TASK_LIMIT` | 16 | Integer 1–64 nondeleted tasks |
| `KESTRI_BACKGROUND_QUEUE_LIMIT` | 8 | Integer 1–32 queued/running background runs |
| `KESTRI_SCHEDULER_INTERVAL_SECONDS` | 5 | 1–60 seconds between due checks |

### Maintenance

| Variable | Bot/data default | Validation / meaning |
| --- | --- | --- |
| `KESTRI_ARCHIVE_RETENTION_DAYS` | 90 | Integer 1–3650 |
| `KESTRI_EVIDENCE_RETENTION_DAYS` | 30 | Integer 1–3650 |
| `KESTRI_LOG_RETENTION_DAYS` | 30 | Integer 1–3650; events, not a file logger |
| `KESTRI_BACKUP_RETENTION_DAYS` | 30 | Integer 1–3650; recognized managed backup files |
| `KESTRI_MAINTENANCE_INTERVAL_SECONDS` | 3600 | Integer 60–86400; cleanup defers while busy |

### Independent embedding configuration

`EmbeddingSettings` requires only `DASHSCOPE_API_KEY` and `KESTRI_EMBEDDING_BASE_URL`; every other field/default is cataloged in the [embedding reference](embedding.md). No DeepSeek, Telegram, or database credentials are required. `DataSettings`/`ResearchSettings` also read the optional DashScope key for configured-secret redaction only; this does not activate embeddings. The command validates the connection without automatic memory or vector tables.

## Fixed application limits

The following constants are not additional supported environment variables: Telegram poll batch 20; result chunk 3500 characters; send attempts at most 3; send delay clamped to 1–120 seconds; selected background retry once after 30 seconds; catch-up 21600 seconds; URL 2048 characters; page retention 64000 characters; HTTP JSON 2000000 bytes; DNS JSON 65536 bytes; backup 64 MiB/50000 rows; creation content allowance 32 MiB; recent runs 5; archive listing 10 with 500-character previews and explicit 3000-character pages; reply evidence references 20. Review the owning implementation before making these configurable.

`KESTRI_TEST_DATABASE_URL` is test harness configuration, not an application setting. Tests capture it before environment isolation, require loopback and database name `kestri_test`, and drop the business schema. See [run checks](../how-to/run-checks.md).

## Outputs and exit codes

| Exit | Meaning |
| --- | --- |
| 0 | Command completed successfully; smoke additionally passed its verification |
| 1 | Startup/execution/evidence error or failed smoke verification |
| 2 | Argument parsing or configuration validation error |
| 130 | CLI-managed interruption/cancellation |

Data commands print JSON: status gives `counts` and `last_maintenance`; backup/export gives absolute `path` and `private=true`; restore gives row/file counts and policy; cleanup gives cutoffs/counts and whether deferred. Preview success is not proof that import SQL, foreign keys, or disk writes will succeed during apply. The bot is long-running and prints a startup identity notice, not per-model traces. Smoke prints the evidence path and verification result. Errors report class/category and suppress raw private exception bodies.

For algorithms behind these contracts, read [execution/delivery](../design/execution-and-delivery.md), [model/accounting](../design/model-and-accounting.md), [task scheduling](../design/task-scheduling.md), [context](../design/context-management.md), and [data maintenance](../design/data-maintenance.md).

## Automatic-memory configuration

The four `ResearchSettings` extraction limits and owner commands are listed in [memory/context](memory-and-context.md). `KESTRI_MEMORY_LIMIT` now counts active explicit-command entries; queued/running foreground capacity excludes maintenance runs. No environment switch silently opts the owner into automatic extraction.

## Product embedding and semantic recall

`ResearchSettings` now reads optional Beijing embedding connection fields and the accounting/retrieval settings in [semantic memory](semantic-memory.md). Product dimensions are fixed at 1024; standalone `EmbeddingSettings` retains its broader smoke contract. Blank/missing product key or missing URL does not activate embeddings. Invalid supplied product configuration fails validation. `/memory semantic on` requires configured embedding and an available vector table; there is no environment opt-in to private indexing. Logical backups now use schema 6 and accept schema 4/5/6.
