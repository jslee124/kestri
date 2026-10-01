# M1 Telegram research reference

[简体中文](telegram.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Scope: implemented `kestri telegram` and `kestri telegram-id`. Full live acceptance status is tracked in the [M1 record](../development/m1-validation.md).

## Configuration

Process environment overrides `.env` in the current working directory. Names are case-insensitive; unknown keys are ignored. Invalid values stop startup. Secrets are application configuration, excluded from model prompts. `kestri telegram-id` requires only `TELEGRAM_BOT_TOKEN`.

| Variable | M1 default | Meaning / accepted range |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | Required | Nonblank official API credential |
| `TELEGRAM_BOT_TOKEN` | Required | BotFather token; numeric prefix and valid token suffix |
| `TAVILY_API_KEY` | Required | Nonblank API credential |
| `DATABASE_URL` | Required | PostgreSQL connection DSN; schema/table creation required |
| `POSTGRES_PASSWORD` | Required by Compose | Strong URL-safe password; use the same password in local DSN |
| `KESTRI_TELEGRAM_OWNER_ID` | Required | Positive numeric user ID; private chat ID must match |
| `KESTRI_MODEL` | `deepseek-flash` | Model identifier, 1–100 characters |
| `KESTRI_THINKING_MODE` | `disabled` | `disabled` or `enabled` |
| `KESTRI_MAX_MODEL_CALLS` | `8` | 1–20 attempts per run |
| `KESTRI_MAX_TOOL_CALLS` | `8` | 1–20 attempts per run |
| `KESTRI_RUN_TIMEOUT_SECONDS` | `120` | Greater than 0, at most 300; research deadline |
| `KESTRI_REQUEST_TIMEOUT_SECONDS` | `30` | Greater than 0, at most 120; DeepSeek/Tavily timeout |
| `KESTRI_MAX_OUTPUT_TOKENS` | `4096` | 64–8192 per model response |
| `KESTRI_INPUT_TOKEN_BUDGET` | `128000` | 4096–256000; conservative request admission estimate |
| `KESTRI_TOOL_OUTPUT_CHARS` | `12000` | 2000–32000; model-visible tool JSON limit |
| `KESTRI_MAX_REPLY_CHARS` | `12000` | 1000–16000; answer display target before notice/chunking |
| `KESTRI_WORKSPACE_DIR` | `.kestri/workspace` | Operator-selected evidence root; Compose uses `/workspace` |
| `KESTRI_URL_DNS_MODE` | `system` | `system` or `cloudflare`; public-URL DNS verification |
| `KESTRI_QUEUE_LIMIT` | `8` | 1–32 queued plus running research requests |
| `KESTRI_MONTHLY_BUDGET_USD` | `20` | Greater than 0, at most 1000; UTC-month local envelope |
| `KESTRI_RUN_BUDGET_USD` | `0.50` | Greater than 0, at most 20; local run envelope |
| `KESTRI_INPUT_USD_PER_MILLION` | `0.30` | Greater than 0, at most 100; input estimation rate |
| `KESTRI_OUTPUT_USD_PER_MILLION` | `1.20` | Greater than 0, at most 100; output estimation rate |
| `KESTRI_SEARCH_CREDIT_USD` | `0.008` | Greater than 0, at most 1; Tavily credit estimation rate |

The shared variable names override both M0 and M1. M0's smaller defaults remain in its [reference](configuration.md); the current `.env.example` explicitly selects M1 limits. Standard `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` are transport settings honored by HTTP clients. A loopback proxy on the host is not the same address inside a container; use an appropriate reachable address such as `host.docker.internal` where supported. Never expose proxy credentials in diagnostic output.

## Commands and associations

The owner’s private chat uses Telegram’s native collapsible command menu. It lists every supported slash command: `/start`, `/status`, `/runs`, `/usage`, `/stop`, `/new`, `/help`, `/tasks`, and `/task`, with English descriptions and a Chinese translation for Chinese-language clients. Startup registers the menu only for the configured owner; each response removes the old reply keyboard. Selecting a command uses the same authentication, archiving, and handling as typing it. Status/list/help commands do not call the model; `/task` interpretation does. Menu appearance depends on the Telegram client. `/new` preserves history and is refused while foreground work is queued or running.

| Interface | Behavior |
| --- | --- |
| Ordinary text | Archive, queue, acknowledge, and run; continue latest completed context |
| Reply with text | Include known completed result and its evidence references; unknown/incomplete result fails explicitly |
| `/start`, `/help` | Explain capabilities, controls, and external services; no model call |
| `/stop`, exact `stop` / `停止` / `停止当前执行` / `停止当前任务` / `停下` | Stop foreground run; a reply selects the referenced known queued/running run |
| `/status`, `/runs` | Latest five runs, status, evidence/usage counts, delivery problems, safe error type |
| `/usage` | UTC-month recorded estimates plus outstanding/unknown reservations; not a provider bill |
| `/new` | Clear committed context only when no queued/running work; preserve records |
| Other slash commands | Unsupported-command notice; no model call |

Polling continues while one research worker runs. Authentication requires the configured owner, a matching private chat, and a non-bot sender before personal persistence or model work. Unauthorized messages are ignored; the service cursor can advance past them without archiving their content. A database is bound to one bot/owner pair and refuses a changed pair; there is no identity-migration command in M1.

## Controlled information tools

`search_web(query, topic)` accepts a strict query of 1–500 characters and `general` or `news`. It requests basic search with at most five results, without provider-generated answers or automatic parameter selection. Snippets retain provenance and are labeled untrusted.

`extract_pages(urls)` accepts one to three public URLs, validates all before spending, and requests basic text extraction. Missing, failed, or empty pages are recorded as failed. Successful material is retained up to 64,000 characters per page; excerpts are bounded and truncation is explicit. `read_evidence(evidence_id)` reads bounded retained material from the current run or a completed run in the same chat. Models cannot supply arbitrary paths or overwrite/delete files.

Only HTTP(S), standard web ports, and public resolved addresses are accepted. Credentials, selected secret query parameters, localhost/private/link-local addresses, malformed forms, and mapped IPv6 addresses are rejected. Local DNS checks do not guarantee Tavily's remote DNS/redirect destinations; extraction remains a delegated provider trust boundary. The application does not locally fetch arbitrary pages.

System DNS is the default. Fake-IP proxies can cause public sites to be correctly rejected. Explicitly set `KESTRI_URL_DNS_MODE=cloudflare` to verify A/AAAA records through the fixed [Cloudflare DoH JSON API](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/) (checked 2026-10-01). This discloses candidate page hostnames to Cloudflare using a separate client without service credentials. Literal IPs are still validated directly and resolved private addresses still fail; DNS failures never fall back to a weaker mode. This mode applies only to delegated remote extraction; a future local fetcher must validate its actual connection and each redirect.

Provider responses are bounded to 2 MB. Oversized tool serialization fails safely rather than supplying malformed JSON. Fixed service endpoints are used; model tools cannot change provider URLs. Stored evidence and answers redact configured credential values. LangSmith tracing is disabled for research; checkpoints can still contain internal model reasoning and must be treated as private data.

## Durable execution and delivery

Runs move from `queued` to `running`, then `completed`, `failed`, `cancelled`, or `interrupted`. Only a completed run advances the committed conversation pointer. Each run uses a fresh graph thread seeded from the last committed checkpoint; original inbound/outbound messages are archived separately. No automatic trimming or compression is implemented.

Acceptance and update deduplication are transactional. Cursor advancement follows durable handling. Results and outgoing chunks are saved before sending. Restart retains queued requests and saved results, marks unfinished runs interrupted, and converts in-flight sends to `uncertain`. Interrupted research is not automatically rerun.

Messages are plain text with link previews disabled, split into 3500-character chunks, preserving queued order and reply association. Explicit non-delivery such as HTTP 429 or a connection failure can retry the saved message up to three total attempts, with bounded delay. Ambiguous timeouts/malformed success responses become `uncertain` and are not automatically resent. `/runs` exposes failures/uncertainty; M1 has no manual resend/reconciliation command. A database cannot guarantee exactly-once Telegram delivery.

## Budget and context accounting

Before a model request, UTF-8 serialized message/tool bytes plus fixed overhead provide a deliberately conservative input estimate, including system/tool/reasoning material. This is an admission heuristic, not DeepSeek's exact tokenizer or a use of its full advertised context window. Oversized context stops with a notice; `/new` can start fresh context.

Before billable work, a database-serialized reservation checks monthly and per-run limits. Model reservations use estimated input and maximum output at configured rates; available response token usage replaces the reservation estimate. Search reserves one Tavily credit; a basic extraction batch of at most three pages reserves one credit. Search/extraction keep that conservative amount even when provider-reported usage is lower. Unfinished or unknown calls retain their reservation.

Default model rates are conservative peak, uncached estimates checked against [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/) on 2026-10-01. The search-credit rate is configurable and is not a claimed plan-specific invoice price. Update rates for your account/provider. Discounts, caching, unknown external completion, and estimate error mean local envelopes are not provider-side billing guarantees. Automatic SDK model retries are disabled.

## Deployment and data lifecycle

Base Compose runs a non-root application with read-only root, writable named workspace volume, bounded `/tmp`, dropped capabilities, no added privileges, CPU/memory/PID limits, and no Docker socket or host-home mounts. PostgreSQL uses a separate named volume and an internal network with no published port. `compose.dev.yaml` intentionally publishes a loopback port for local development. Containers do not sandbox controlled tools independently of application privileges.

Canonical records live in the `kestri` schema; LangGraph owns separate checkpoint tables. Workspace text is organized by generated run/evidence UUIDs with no-follow relative file operations. Cleanup, retention enforcement, export, backup, restore, and memory are deferred. Design retention values are proposals, not automatic deletion. `docker compose stop` preserves volumes; `down -v` deletes durable data and should not be used as a routine stop command.

M2 adds `/tasks` and `/task` alongside every existing command in the native collapsible menu; see the [task reference](tasks.md) for task control and scheduling rules.
