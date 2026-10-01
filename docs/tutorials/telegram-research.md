# Research through Telegram

[简体中文](telegram-research.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Scope: M1 setup and research. The live research workflow is verified within the scope of the [validation record](../development/m1-validation.md).

## Prepare local configuration

Install Python 3.14 through [uv](https://docs.astral.sh/uv/getting-started/installation/) and a Docker engine with Compose. Start that engine. From the repository root:

```sh
uv sync --locked
cp .env.example .env
chmod 600 .env
```

If `.env` already exists, edit it instead of copying over it. Fill in `DEEPSEEK_API_KEY` and `TAVILY_API_KEY` locally. Research sends selected dialogue/tool context to DeepSeek, queries and URLs to Tavily, and messages through Telegram. Real calls consume service credits.

Set `POSTGRES_PASSWORD` to a new strong, URL-safe password, for example one generated with `uv run python -c 'import secrets; print(secrets.token_hex(24))'`. This command prints a credential: copy it directly into local configuration. Do not post it in chat or commit it. For the local development path below, put the same password into `DATABASE_URL`:

```text
postgresql://kestri:YOUR_PASSWORD@127.0.0.1:55433/kestri
```

The container path overrides this DSN with its internal database address. The example uses research limits of 8 model calls, 8 tool calls, 120 seconds, and 4096 output tokens. See the [M1 reference](../reference/telegram.md) before changing budgets.

## Create the bot and select its owner

In Telegram, open the verified [BotFather](https://t.me/BotFather), send `/newbot`, and follow its name/username prompts. Store the generated token only as `TELEGRAM_BOT_TOKEN` in `.env`. Creating a bot does not authorize anyone to use Kestri.

Open your new bot, send `/start` yourself, then run:

```sh
uv run kestri telegram-id
```

The command prints observed private user IDs without enrolling them, acknowledging the updates, or calling a model. Set `KESTRI_TELEGRAM_OWNER_ID` to **your own numeric user ID**; do not select an unknown sender. IDs are identity data, not API credentials. Research requires both that sender ID and a private chat whose ID matches it.

Do not configure a webhook or run another poller for this bot. Kestri refuses an existing webhook and another Kestri instance sharing the database/bot lock. A separate poller using another database is outside that lock's protection.

## Start the local workflow

For a Python development run:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
uv run kestri telegram
```

This publishes PostgreSQL on loopback port 55433 for the local Python process. It does not isolate that process from your host. For the container deployment instead:

```sh
docker compose up --build -d
docker compose logs -f app
```

Use one application process at a time. If you previously used the development database override and now want no published database port, stop the local Python process and run `docker compose up -d --force-recreate postgres app` using the base file. Existing named volumes remain. Confirm the absence of a database port with `docker compose ps`.

The startup line identifies the bot and says owner-only private chat. Missing or invalid configuration fails before research. M1 creates its own schema and LangGraph checkpoint tables; PostgreSQL must allow those operations.

## Research and follow up

Open the Menu beside the input field to see all commands, including `/runs` and `/start`; close it to return to normal chat. If the old reply keyboard is still visible, send `/help` to remove it. Selecting a menu command has the same effect as typing it. `/stop` cancels work, and `/new` starts fresh context only when idle while preserving history.

Send: “Use official LangChain documentation to explain the relationship between agents and checkpoints. Cite the pages you read.” Expect an acknowledgement and a saved answer with source links. The application adds retrieval status independently of the model's prose: snippet only, extracted excerpt, truncated saved material, or extraction failed.

Reply to an answer with: “Which part is an engineering inference?” The reply associates the result and its evidence references with the new request. A normal message continues the latest successfully committed dialogue. Failed, stopped, and interrupted turns do not become the conversation's committed head.

Send `/status`, `/runs`, and `/usage` to inspect outcomes. During a long request, send `/stop`; replying with `/stop` targets that known run. Cancellation stops local waiting and new work, but already-submitted external requests may still incur charges. `/new` starts fresh model context when no work is active or queued; it retains the archive and evidence.

## Stop and understand the limits

Stop a local foreground process with Ctrl+C, or run `docker compose stop app`. Start it again using the same command/volumes. Completed context/results survive; queued accepted requests remain eligible, while interrupted running requests are reported and not automatically researched again. Uncertain Telegram sends are quarantined rather than blindly resent.

Recurring tasks are covered by the [M2 briefing tutorial](recurring-briefing.md). Personal memory and automatic compression are available in M3; start with the [memory tutorial](personal-memory.md). Cleanup, backup/restore, shell, and desktop control remain unavailable. Unsafe compression/context overflow stops with a notice; `/new` begins fresh context and preserves memory. Read the [security design](../design/security-and-data.md) and [reference](../reference/telegram.md) for the remaining boundaries.
