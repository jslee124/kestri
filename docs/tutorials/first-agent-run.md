# Run your first Kestri agent

[简体中文](first-agent-run.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Scope: the implemented M0 developer CLI.

You will run a real LangChain agent, observe a controlled tool interaction, and verify a follow-up that uses the previous result. This exercise sends two fixed arithmetic prompts to DeepSeek and consumes API credits.

## Prepare the checkout

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone the repository:

```sh
git clone https://github.com/jslee124/kestri.git
cd kestri
uv sync --locked
```

uv reads `.python-version` and installs Python 3.14 when necessary, creates `.venv`, and installs the locked dependencies. Python 3.14 is the project baseline; this tutorial does not require changing your system Python.

## Configure your model key

```sh
cp .env.example .env
```

Open `.env` locally and set `DEEPSEEK_API_KEY` to your DeepSeek API key. Keep it out of chat messages and commits. `.env` is ignored by Git. On macOS/Linux, you can restrict its permissions with `chmod 600 .env`.

Leave the other values at their defaults for this exercise. [Configuration reference](../reference/configuration.md) describes their exact meanings.

## Run the two-turn check

```sh
uv run kestri smoke
```

The first turn asks the model to add 17 and 25 using `checked_add`; the second asks it to add 8 to the previous result. A successful run prints:

```text
Evidence: .kestri/evidence/smoke-<unique-id>.json
PASS: real tool interaction and multi-turn follow-up verified.
```

Open the reported JSON file. Confirm that the tool results are `42` and `50`, each turn is verified, and model usage metadata is present. Each turn normally needs two model requests: a tool request followed by an answer after the tool result. Actual request counts can vary within the configured limits.

The evidence omits raw reasoning, request headers, credentials, and exception bodies. The default evidence directory is ignored by Git; evidence files are created with owner-only permissions on POSIX systems.

## Observe the boundary

The agent has one bounded arithmetic tool. It cannot browse, run shell commands, read your files, or send Telegram messages. Its conversation checkpoint exists only in this process; rerunning the command starts a new session.

To repeat the exercise with thinking enabled, change `KESTRI_THINKING_MODE=enabled` in `.env` and run the same command. Kestri preserves the provider's required reasoning state internally while excluding its text from the evidence file. Each repeat consumes additional API credits.

Press Ctrl+C to cancel. A configuration error exits with code 2; a failed check exits with code 1; a completed check exits with code 0. The CLI suppresses raw exception details. For a failure, inspect the recorded status and error type if an evidence file was produced; confirm credentials and network access before retrying.

Continue with [running offline checks](../how-to/run-checks.md) or read the [M0 validation record](../development/m0-validation.md). Telegram research is the next [milestone](../development/milestones.md).
