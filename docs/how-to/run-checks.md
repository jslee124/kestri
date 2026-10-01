# Run the offline checks

[简体中文](run-checks.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Scope: the implemented M0 development checks.

## Check a change

From the repository root, with [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```sh
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest -q
uv run python scripts/check_docs.py
```

These checks do not require credentials or contact a model provider. Runtime tests use HTTP mock transports with the actual LangChain agent and DeepSeek SDK serialization. They test tool-result continuity, provider reasoning replay, failures, limits, timeout, cancellation, and evidence handling. They do not establish live model behavior.

The documentation check covers translation partners, counterpart links, local file links, heading counts, and engineering identifier sets. It does not assess translation quality, external links, or Markdown anchors; review those separately.

## Check the package build

```sh
uv build
```

This produces a source distribution and wheel in `dist/`. It does not publish a package or verify Telegram/deployment behavior.

## Check the real provider separately

Use the [first-run tutorial](../tutorials/first-agent-run.md) when a live integration check is needed. It requires a local API key and consumes API credits. Keep the distinction between offline results and live evidence in the validation record.

The [GitHub Checks workflow](../../.github/workflows/checks.yml) runs the offline commands and package build on Linux with Python 3.14. It does not receive the developer's `.env` or call DeepSeek. Inspect a completed run before claiming remote CI success.
