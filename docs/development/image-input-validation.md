# Image input validation

[简体中文](image-input-validation.zh-CN.md) · [Design](../design/image-input.md)

## Local result

2026-10-03, branch `codex/telegram-image-input`. Full suite: **343 passed, no skips**,
using a dedicated disposable PostgreSQL 17 database with pgvector, Python 3.14,
and offline Telegram/DeepSeek HTTP transports. The automated suite did not use the personal deployment or its database.
Separate authorized live acceptance used the upgraded deployment, as described below.

Ruff lint/format, strict mypy (`src` and `scripts`), bilingual documentation,
SQL readability, the 25-case controls evaluation, and source/wheel builds passed.
The wheel contains `agent/images.py` and migration `011_image_inputs.sql`.

## Behavior established

The 28 image checks cover actual decoded PNG/JPEG/WebP; invalid, truncated, animated,
oversized and unsafe inputs; private files; isolated Telegram/web credentials; redirects and bounded streaming; owner/private
authorization; one selected photo size; image documents; album ordering, deduplication,
restart, collection ceilings, count limits and late arrivals; text waiting behind an album;
caption control/memory exclusion; outgoing multiple image blocks through the locked
DeepSeek adapter; visual follow-up; ephemeral pixels with both in-memory and PostgreSQL
checkpoints; the actual summary state-update hook retaining image references; missing,
expired, unauthorized and tampered images; total size admission; backup/export byte
parity and hash validation; restored pending downloads; erase and retryable file cleanup.

Existing research, tasks, memory, semantic history, checkpoint schemas and legacy
backup restoration also pass. Image records are included in backup schema 9; restored
unfinished work stays quarantined under the existing policy.

## Reproduction

Use the dedicated `kestri_test` database required by the test fixtures. Do not point
tests at a personal database: fixtures drop the application schema.

```sh
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src scripts
KESTRI_TEST_DATABASE_URL=postgresql://postgres:test-password@127.0.0.1:5432/kestri_test uv run pytest -q
uv run python scripts/check_docs.py
uv run python scripts/check_sql_readability.py
uv run python scripts/evaluate_controls.py
uv build
```

## Live acceptance

Authorized synthetic-image checks passed against the real DeepSeek provider and the
upgraded Telegram deployment. A two-photo album produced one acknowledgement and one
answer identifying both colors, shapes and numbers in order. After restarting the app,
a text follow-up correctly identified the second image's number. Sending a static PNG
as a Telegram file also returned the correct color, shape and number.

Database checks established that the album created one completed run, both image records
were ready, delivery completed once, and its checkpoints retained no image data URLs.
Before upgrading, a backup was created with the previous app image. The app and original
PostgreSQL volume are healthy with pgvector enabled; deployment uses `compose.vector.yaml`.
Raw provider responses, screenshots and backup details remain ignored under `.kestri/`.

Acceptance found that image downloads reused the Tavily-authenticated web client. The
app now passes its dedicated Telegram client into the research agent; fallback callers
create a separate client without web authorization headers. The multi-photo integration
check now uses a separately authenticated web transport and asserts that Telegram
requests carry no Authorization header.

## Evidence limits

These checks establish a short synthetic session, not general visual accuracy or
long-term daily-use reliability. Remote CI has not been run. Album completion uses a bounded timing heuristic because
Telegram provides no completion event. Active image context is limited to 10 images
and 20 MiB; `/new` resets that context. Summary text describes previous dialogue;
subsequent visual calls inspect retained original files instead of relying on summary
text as proof of image content.
