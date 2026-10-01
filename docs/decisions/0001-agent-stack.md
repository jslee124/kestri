# ADR-0001: Use Python, LangChain Agent, and the DeepSeek official API

[简体中文](0001-agent-stack.zh-CN.md) · [Documentation](../README.md)

- Status: Accepted
- Decision date: 2026-09-30
- Updated: 2026-10-01
- Implementation: Not started; provider compatibility unverified

## Context

The author previously developed [Forge](https://github.com/jslee124/forge), a separate TypeScript coding-agent project for studying agent runtimes and harness internals. That experience informs Kestri's focus on building a usable personal-agent application with an established framework.

Kestri needs a mature agent framework for a usable local personal assistant. The author also wants to learn Python and keep everyday model usage affordable.

## Decision

Use Python and LangChain Agent, with underlying LangGraph persistence and execution control. Use DeepSeek's official API as the first model provider. Kestri is a standalone project with no code or runtime dependency on Forge.

Use one configured model initially, including for ordinary conversation, information processing, and context summarization. Keep provider/model configuration replaceable; do not introduce automatic model routing or a second core agent loop in the first version.

LangChain's agent harness is built on LangGraph; this relationship is documented in the [official overview](https://docs.langchain.com/oss/python/langchain/overview). Framework primitives do not replace Kestri's authorization, task management, or delivery logic.

The initial suggested model ID is maintained with other adjustable values in [architecture](../design/architecture.md). DeepSeek currently documents tool calling and a 1M context window. Capabilities were checked on 2026-09-30; exact model/integration behavior must be verified during implementation. See [DeepSeek's official documentation](https://api-docs.deepseek.com/quick_start/pricing/).

## Alternatives considered

| Alternative | Reason not selected initially |
| --- | --- |
| TypeScript with the same framework | A viable direction, but Python better matches the owner's present learning goal |
| A custom runtime or Forge integration | Duplicates runtime work and couples an independent personal-agent project to Forge |
| Pi SDK as the core harness | A different core runtime choice; combining agent loops creates additional state and control boundaries without a current need |
| Deep Agents immediately | Its broader harness is not required by the first controlled-tool workflows; reassess when actual capabilities justify it |
| Claude or GPT as the primary provider | The owner prefers a Chinese provider and lower recurring costs for daily tasks |
| Local model inference | Adds hardware and model-serving work outside the initial application-learning focus |

## Consequences

The project can concentrate on tools, persistence, memory, and ongoing tasks while learning Python. Costs and quality still depend on actual workloads and provider behavior; the design does not establish a comparative model benchmark.

DeepSeek tool calls, thinking-mode state, token estimation, summarization, retries, and cancellation need integration validation. API format compatibility alone is insufficient evidence.

Replacing the core harness later may require reviewing state, prompts, middleware, tool permissions, and checkpoints. Deep Agents remains an option, not a promised drop-in upgrade. Reusable application services should not depend on a particular agent loop unnecessarily.

Local operation does not eliminate external processing: assembled context is sent to the chosen provider. See [security and data](../design/security-and-data.md).

## Review conditions

Reconsider when observed task quality, compatibility, cost, or workflow complexity requires a different model or harness. Record a superseding ADR for a major stack change. Routine model settings and context budgets remain adjustable without replacing this decision.
