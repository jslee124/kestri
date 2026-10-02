# Repository layout

[简体中文](repository-layout.zh-CN.md) · [Docs](../README.md)

## Source ownership

| Package | Responsibility |
| --- | --- |
| `src/kestri/agent/` | Model adaptation, research graph, budget/control, context, smoke and minimal runtime |
| `src/kestri/memory/` | Personal facts, extraction proposals, repositories/workers, vector indexing and recall |
| `src/kestri/history/` | Owner-scoped archive search/read and historical vector recall |
| `src/kestri/tasks/` | Task intent, agreement execution and recurrence scheduling |
| `src/kestri/storage/` | PostgreSQL store, migrations, backup/retention and scoped evidence files |
| `src/kestri/integrations/` | Telegram, public-web tools, embedding transport, HTTP and URL policy |

`cli.py`, `settings.py`, `errors.py`, `redaction.py`, and `application.py` stay at the package root as entry/configuration/shared boundaries and application composition. Import concrete modules; package initializers do not re-export implementations or create compatibility wrappers. This is an internal module-path change, not a promised SDK API migration. The CLI command and persisted SQL names are unchanged.

Agent orchestration composes domain services and integrations. Domain code receives owner identity and scoped dependencies from the application; providers do not decide owner authorization. PostgreSQL primitives stay in storage; SQL migrations remain ordered and packaged as resources under `storage/sql/`. Moving files does not change the database schema or migrate production data. Larger shared store methods can be extracted later when a stable transaction boundary is clear; this refactor avoids splitting transactions merely to shorten files.

## Tests and documentation

Tests mirror domain packages under `tests/agent`, `memory`, `history`, `tasks`, `storage`, and `integrations`. Shared isolated fixtures remain in `tests/conftest.py` and helpers in `tests/helpers.py`; tests import helpers by their absolute package name. Configuration tests stay at the test root. The normal `pytest` command discovers all folders.

The [implementation guide](implementation-guide.md) links to current concrete source paths. Historical validation records retain their original evidence boundaries even when links follow moved source files. Runtime references own behavior contracts; design documents own target architecture. Run [checks](../how-to/run-checks.md) after moving modules, including both PostgreSQL variants, docs links, and wheel resource checks.

## Readability

Use four-space SQL indentation, one table column or assignment per line, and separate boolean conditions. Name local rows by their purpose; keep nested trigger branches aligned. Add short comments for consent, invalidation, leases and cost boundaries. `python scripts/check_sql_readability.py` checks tabs, indentation and 100-column width in CI; it is a formatting guard, not a SQL parser or a substitute for review. Embedded Python queries should use multiline SQL when joins or authorization conditions become complex.
