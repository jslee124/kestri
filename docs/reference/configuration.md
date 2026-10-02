# M0 configuration reference

[简体中文](configuration.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Scope: `kestri smoke`, implemented in `src/kestri/settings.py` and `src/kestri/agent/runtime.py`.

## Configuration sources

Run from the project root. Process environment values take precedence over `.env` in the current working directory; defaults apply when neither supplies a value. Names are case-insensitive. Unknown `.env` keys are ignored. Invalid supported values stop the CLI before model work.

| Variable | Default | Accepted values and meaning |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | Required | Nonblank API credential; never included in agent prompts |
| `KESTRI_MODEL` | `deepseek-flash` | Nonempty model identifier, at most 100 characters; alternatives need their own validation |
| `KESTRI_THINKING_MODE` | `disabled` | `disabled` or `enabled`; explicitly sent to the provider |
| `KESTRI_MAX_MODEL_CALLS` | `4` | Integer 1–20; model-call attempts per conversation turn |
| `KESTRI_MAX_TOOL_CALLS` | `4` | Integer 1–20; tool-call attempts per conversation turn |
| `KESTRI_RUN_TIMEOUT_SECONDS` | `60` | Number greater than 0 and at most 300; time allowed for one agent turn |
| `KESTRI_REQUEST_TIMEOUT_SECONDS` | `20` | Number greater than 0 and at most 120; SDK HTTP timeout setting, subordinate to the turn deadline |
| `KESTRI_MAX_OUTPUT_TOKENS` | `1024` | Integer 64–8192; provider `max_tokens` per model request |
| `KESTRI_EVIDENCE_DIR` | `.kestri/evidence` | CLI evidence directory; relative paths resolve from the working directory |

The evidence directory is operator configuration, not a model-controlled filesystem capability. If you choose a different path, manage its permissions and Git exclusion yourself. The evidence writer restricts new directories and files on POSIX systems; it does not tighten existing directory permissions.

## Fixed M0 behavior

- Official endpoint: `https://api.deepseek.com/v1`. `DEEPSEEK_API_BASE` does not override the application's endpoint.
- SDK automatic retries: zero. Limits apply per turn, so the two-turn smoke may attempt up to twice the model-call allowance overall.
- LangChain model/tool limit middleware stops the run when a new call would exceed its allowance. A failed or cancelled session cannot accept another turn.
- Application tracing through LangSmith is disabled for this run, including when enabled in the parent environment.
- Agent state uses a process-local LangGraph `InMemorySaver`. This smoke has no cross-process recovery or canonical message archive; M1 separately implements both.
- `checked_add` accepts two strict integers within ±1,000,000. Unknown fields are rejected; the sum must also lie in that range. The tool does not access files, networks, or a shell.

The provider adapter preserves `reasoning_content` on earlier assistant messages and normalizes empty assistant tool-call content. This compensates for the locked integration's outbound serialization and is covered by payload-level regression tests. DeepSeek documents reasoning replay for requests carrying tools in its [thinking-mode guide](https://api-docs.deepseek.com/guides/thinking_mode/) (checked 2026-10-01).

## Results and evidence

Run statuses are `completed`, `timeout`, `model_limit`, `tool_limit`, `provider_error`, or `internal_error`. A smoke passes only when both turns complete, contain a successful expected tool result, and answer with the expected number. A `completed` agent turn can still fail smoke verification.

CLI exit codes: 0 for a passed check, 1 for a failed check or execution/evidence error, 2 for invalid configuration or arguments, and 130 for Ctrl+C cancellation. The CLI reports exception type without raw exception messages. Cancellation before completion may leave no evidence file.

Evidence schema version 1 includes the UTC timestamp, Python/package versions, provider/model/mode, configured limits, per-turn status/time, model-response counts, tool calls/results, available token usage, reasoning-presence booleans, answers, and verification outcome. It omits reasoning text and authentication data. Token usage is provider metadata, not an exact price or bill.

## Other application settings

This document describes only `kestri smoke`. The product implements input admission, context compression, spending reservations, Telegram, Tavily, PostgreSQL, scheduling, and data maintenance; these controls do not apply to smoke. See [CLI and complete configuration](cli.md) for every command/settings class and [model and accounting](../design/model-and-accounting.md) for model adaptation and the smoke evidence format.
