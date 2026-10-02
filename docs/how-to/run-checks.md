# Run the offline checks

[简体中文](run-checks.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Scope: M0, M1, M2, M3, and M4 development checks.

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

These checks do not require service credentials or contact a model provider. Runtime tests use HTTP mock transports with the actual LangChain agent and DeepSeek SDK serialization. Database tests are skipped unless the dedicated test DSN below is supplied; a run with skips is not full M1 verification.

The documentation check covers translation partners, counterpart links, local file links, heading counts, and engineering identifier sets. It does not assess translation quality, external links, or Markdown anchors; review those separately.

## Test organization and code style

Tests are named by behavior, rather than by the milestone that introduced them:

| Test module | Coverage | Original milestone |
| --- | --- | --- |
| `tests/agent/test_research_integration.py` | Telegram research, persistence, budgets, delivery, and recovery | M1 |
| `tests/tasks/test_tasks_integration.py` | Recurring task agreements, scheduling, and background execution | M2 |
| `tests/memory/test_memory_context_integration.py` | Explicit memory, revocation, and conversation compression | M3 |
| `tests/storage/test_data_lifecycle_integration.py` | Export, backup, restore, retention, and purge | M4 |

`tests/helpers.py` contains shared mock transports and scenario builders. `tests/conftest.py` provides environment isolation and the disposable database fixture. Test modules do not import other test modules. Milestone names remain in development records to identify historical acceptance evidence.

Use one assignment per line, explicit branches for nested decisions, and one item per line for dictionaries with several fields or calls with several arguments. A trailing comma keeps these structures expanded under Ruff; the line limit remains 100 characters. Run both Ruff checks above before submitting changes.

## Include persistence and recovery checks

Use an isolated disposable PostgreSQL instance. Never use your personal Kestri database: these tests **drop the `kestri` schema** before each case. The fixture requires a loopback hostname and database name `kestri_test`, but the name alone does not make your data disposable.

```sh
docker run -d --name kestri-m1-test-db \
  -e POSTGRES_PASSWORD=kestri-test-only -e POSTGRES_DB=kestri_test \
  -p 127.0.0.1:55432:5432 \
  postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
docker exec kestri-m1-test-db pg_isready -U postgres -d kestri_test
KESTRI_TEST_DATABASE_URL=postgresql://postgres:kestri-test-only@127.0.0.1:55432/kestri_test \
  uv run pytest -q
```

Wait until `pg_isready` reports accepting connections. The test-only password above is not for deployment. Tests cover unauthorized updates, duplicate acceptance, concurrent budget reservations, failed/cancelled/interrupted runs, successful-checkpoint commit, fresh-agent follow-up, reply controls, source attacks, retained failed/truncated material, known-send retries, and uncertain-send recovery. They do not simulate an actual Telegram outage or prove live provider semantics.

After testing, remove only this disposable container:

```sh
docker stop kestri-m1-test-db
docker rm kestri-m1-test-db
```

Do not remove your Compose volumes as part of this workflow.

## Check the package build

```sh
uv build
```

This produces a source distribution and wheel in `dist/`. The wheel must include `kestri/sql/001_initial.sql`, `kestri/sql/002_tasks.sql`, `kestri/sql/003_memory_context.sql`, and `kestri/sql/004_data_lifecycle.sql`. It does not publish a package or verify deployment behavior.

## Check live services separately

Use the [M0 tutorial](../tutorials/first-agent-run.md) for the minimal model/tool integration or [Telegram tutorial](../tutorials/telegram-research.md) for M1. Both need local credentials and consume credits. Keep offline, live service, and container evidence distinct in the [M1 record](../development/m1-validation.md).

The [GitHub Checks workflow](../../.github/workflows/checks.yml) runs these commands and package build on Linux with Python 3.14 and a disposable PostgreSQL service. It receives no developer `.env` and calls neither DeepSeek nor Tavily nor Telegram. Inspect a completed run before claiming remote CI success.

## Automatic-memory checks

The same disposable PostgreSQL suite now includes [test_memory_jobs_integration.py](../../tests/memory/test_memory_jobs_integration.py). Check that the wheel also contains `kestri/sql/005_automatic_memory.sql`. No test in this increment opts in the owner's running installation or uses real private chat with a provider.

## Semantic-memory checks

[Semantic unit](../../tests/memory/test_semantic_memory.py) and [integration tests](../../tests/memory/test_semantic_memory_integration.py) add a required vector-capable CI leg beside plain PostgreSQL. Build the checksummed optional extension image with `docker build -f docker/postgres-vector.Dockerfile -t kestri-postgres-vector:17-pgvector-0.8.7 .`, then run it as a disposable `kestri_test` server using the same isolated port/credentials pattern above. Vector tests skip in the plain leg; they must run without skips in the vector leg. Neither image should reuse personal data. The wheel must include `006_semantic_memory.sql`, `memory_embedding.py`, `memory_index.py` and `memory_retriever.py`. [Semantic runtime reference](../reference/semantic-memory.md) separates deployment/quality evidence from these checks.
