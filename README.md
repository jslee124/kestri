# Kestri

[简体中文](README.zh-CN.md)

Kestri is a local personal AI agent, accessible through a Telegram bot. It is intended to help with everyday questions, information research, personal preferences, and explicitly delegated recurring tasks.

The working name comes from **kestrel**, with the possibility of a character or mascot in the future.

## Project status

**M0 verified.** A Python 3.14 CLI runs a bounded, two-turn LangChain agent against DeepSeek with a controlled arithmetic tool. Both non-thinking and thinking modes have live evidence, alongside offline failure and limit checks. Start with the [first-run tutorial](docs/tutorials/first-agent-run.md) and [validation record](docs/development/m0-validation.md).

**M1: Telegram research is implemented and verified.** Owner-only private chat, controlled Tavily tools, PostgreSQL checkpoints/archives, cancellation, usage reservations, and Docker Compose are available. Start with the [Telegram tutorial](docs/tutorials/telegram-research.md), [M1 reference](docs/reference/telegram.md), and [M1 evidence](docs/development/m1-validation.md). Recurring tasks, memory, compression, and full data-lifecycle acceptance remain planned. The [runnable milestones](docs/development/milestones.md) distinguish delivery scope and evidence.

## Goals

- Learn agent application development and engineering practices through a usable product.
- Build an assistant the project owner wants to use regularly.

## First-version direction

The first version focuses on three connected workflows:

1. Research a question using public web sources and continue discussing the findings.
2. Create and manage a recurring news briefing delivered in the same Telegram chat.
3. Explicitly save, inspect, update, and forget personal preferences or facts.

A news briefing is the first acceptance scenario for reusable information tools. Kestri's product scope remains a general personal agent.

## Selected technologies

| Area | Selected direction |
| --- | --- |
| Application | Python 3.14, LangChain Agent, underlying LangGraph persistence and execution control |
| Model provider | DeepSeek official API |
| Interaction | Telegram private chat, long polling, configured user-ID allowlist |
| Web information | Tavily Search and Extract behind Kestri-owned tools |
| Persistence | Local PostgreSQL and a dedicated filesystem workspace |
| Deployment | Docker Compose for the application and database |
| Initial tool policy | Controlled tools; arbitrary code execution deferred |

Local operation means the application and its durable data run locally. Model requests, web retrieval, and Telegram messaging use external services. Data processing boundaries are described in the [security and data design](docs/design/security-and-data.md).

## Documentation

Start with the [documentation guide](docs/README.md). The suggested reading order is product, requirements, architecture, security and data, and then architecture decisions.

English is the primary documentation language. Every English document has a corresponding Simplified Chinese translation, with matching scope, status, and identifiers.
