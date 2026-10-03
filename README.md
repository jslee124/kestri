<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="design/brand/assets/kestri-logo-dark.png">
    <img src="design/brand/assets/kestri-logo.png" alt="Kestri" width="420">
  </picture>
</p>

<p align="center">
  <strong>A personal agent for research, memory, and ongoing tasks.</strong><br>
  <sub>Run it locally. Talk through Telegram. Keep your preferences and task agreements across conversations.</sub>
</p>

<p align="center">
  <a href="https://github.com/jslee124/kestri/actions/workflows/checks.yml"><img src="https://img.shields.io/github/actions/workflow/status/jslee124/kestri/checks.yml?branch=main&amp;style=flat-square&amp;label=CI" alt="CI status"></a>
  <img src="https://img.shields.io/badge/source-v0.1.0-ca7448?style=flat-square" alt="Source version 0.1.0">
  <img src="https://img.shields.io/badge/Python-3.14-63758c?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python 3.14">
  <img src="https://img.shields.io/badge/interface-Telegram-30343b?style=flat-square&amp;logo=telegram&amp;logoColor=white" alt="Telegram interface">
</p>

<p align="center">
  <a href="#get-started">Get started</a> ·
  <a href="#what-kestri-can-do">Capabilities</a> ·
  <a href="#everyday-use">Everyday use</a> ·
  <a href="docs/design/security-and-data.md">Data &amp; security</a> ·
  <a href="docs/README.md">Documentation</a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

Kestri is a local personal AI agent for everyday questions, information research,
personal preferences, and explicitly delegated recurring tasks. It runs on your
own machine and works through an owner-only Telegram private chat.

The project aims to build an assistant worth using regularly while learning and
demonstrating agent application engineering. Its scope is a general personal
agent; news briefings are one practical workflow.

## What Kestri can do

| Capability | What it gives you |
| --- | --- |
| **Research with sources** | Ask a question, retrieve public web information, and follow up on an answer in the same chat. |
| **Personal memory** | Save, inspect, correct, and forget preferences; continue conversations with managed context. |
| **Recurring briefings** | Delegate daily or weekly research with an explicit schedule, timezone, and task agreement. |
| **Execution controls** | Inspect runs and estimated usage, cancel active work, and start fresh conversation context. |
| **Durable state** | Keep completed results, conversation history, memory, and task agreements across restarts. |
| **Data maintenance** | Manage retention, export local data, create backups, and restore conservatively. |

Start with [research](docs/tutorials/telegram-research.md),
[personal memory](docs/tutorials/personal-memory.md), or
[recurring briefings](docs/tutorials/recurring-briefing.md).

## Get started

You need **Python 3.14**, [uv](https://docs.astral.sh/uv/), Docker with Compose,
and access to DeepSeek, Tavily, and a Telegram bot.

Prepare a fresh source checkout:

```sh
git clone https://github.com/jslee124/kestri.git
cd kestri
uv sync --locked
cp .env.example .env
chmod 600 .env
```

Complete the [Telegram setup guide](docs/tutorials/telegram-research.md) before
starting the application. It walks through API keys, the bot token, your owner
ID, and the PostgreSQL password and connection URL. If you already have a local
`.env`, edit it rather than overwriting it.

For a local Python development run:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
uv run kestri telegram
```

For container deployment, follow the
[operations guide](docs/how-to/operate-local-agent.md).
Existing vector-enabled installations should use the
[Memory v2 deployment guide](docs/how-to/deploy-memory-v2.md).

## Everyday use

Open your bot's private chat and try a small request:

```text
Research a topic using public sources, cite the pages you read,
and explain which conclusions are your own inference.
```

Then save a preference:

```text
/remember I prefer concise answers with source links.
```

For a recurring briefing, specify the schedule and timezone:

```text
Every day at 08:00 Asia/Shanghai, send me an AI and technology
news briefing: at most three items, two sentences each, with source links.
```

Inspect the returned task agreement. Use Telegram's collapsible command Menu,
or type the controls directly:

| Command | Purpose |
| --- | --- |
| `/memory` | Inspect saved personal memory |
| `/tasks` | List recurring task agreements |
| `/status` · `/runs` | Inspect current work and run outcomes |
| `/usage` | View local usage and cost estimates |
| `/stop` | Cancel active foreground work |
| `/new` | Start fresh context while preserving memory, tasks, and archives |
| `/help` | See available commands |

## How it works

| Layer | Implementation |
| --- | --- |
| Agent | Python 3.14, LangChain Agent, LangGraph execution and persistence |
| Model | DeepSeek official API |
| Research | Tavily Search and Extract behind Kestri-owned tools |
| Interaction | Telegram private chat, long polling, configured owner allowlist |
| Storage | Local PostgreSQL and a dedicated filesystem workspace |
| Deployment | Docker Compose for the application and database |
| Tool policy | Controlled tools; arbitrary code execution is deferred |

The application and durable data run locally. Model requests, web retrieval,
and Telegram messaging use external services. Sleep, lost connectivity, or a
stopped application can delay scheduled work. Read the
[security and data design](docs/design/security-and-data.md) for processing
boundaries and the [operations guide](docs/how-to/operate-local-agent.md) for
restart and recovery behavior.

## Project status

**The first version (M0–M4) is implemented.** Research and follow-up, recurring
briefings, explicit memory, automatic context compression, and data maintenance
are available. Memory refinements are documented in the
[Memory v2 completion record](docs/development/memory-v2-completion.md).

The [first-version acceptance record](docs/development/first-version-acceptance.md)
separates controlled tests, live API and Telegram checks, deployment, and
session trials. Long-term usefulness and provider quality remain separate
evaluation questions. [Milestones](docs/development/milestones.md) record the
delivery history.

## Documentation

| Goal | Start here |
| --- | --- |
| Set up and use Kestri | [Telegram setup](docs/tutorials/telegram-research.md) |
| Operate and protect local data | [Operations](docs/how-to/operate-local-agent.md) · [Backup and restore](docs/how-to/backup-and-restore.md) |
| Understand the implementation | [Implementation guide](docs/development/implementation-guide.md) · [Architecture](docs/design/architecture.md) |
| Study storage, context, and tools | [Database](docs/reference/database.md) · [Context](docs/design/context-management.md) · [Tools](docs/design/tools.md) |
| Check changes | [Validation guide](docs/how-to/run-checks.md) |
| Use the logo and mascot | [Visual identity](design/brand/README.md) |

The [documentation index](docs/README.md) maps the full collection. English
documents have matching [Simplified Chinese](README.zh-CN.md) translations
with the same scope, status, and engineering identifiers.

Kestri takes its name from **kestrel**, represented by the project's little bird mascot.
