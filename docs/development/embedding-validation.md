# Embedding connection validation

[简体中文](embedding-validation.zh-CN.md) · [Documentation](../README.md)

Date: 2026-10-02. Scope: standalone Beijing DashScope adapter, independent settings, CLI, redaction registration, and Memory v2 specification. Full automatic memory and vector storage remain unimplemented.

## Offline checks

`tests/test_embedding.py` exercises request serialization, reordered output, invalid dimensions/numbers/zero norm/indices/model/usage, input admission, credential-safe errors, redirects, endpoint restrictions, environment dimension parsing, and evidence serialization. The existing test suite also checks shared HTTP behavior and configuration regressions. See [run checks](../how-to/run-checks.md). Final local check outcomes are recorded below after execution; no remote CI or installed-container claim is made.

Final local checks: Ruff lint/format, mypy (26 source files), documentation checks (86 documents), and `git diff --check` passed. Offline suite: 81 passed, 66 skipped; skipped cases require a disposable database, so database integration was not run. The 25 embedding tests cover this increment. No remote CI or running-container replacement was performed. Credential scan found no supplied key in reviewable source/docs; local `.env` mode is 0600.

## Live provider evidence

[Sanitized JSON](evidence/embedding-live.json) records one request on 2026-10-02 at 05:47:30 UTC (13:47:30 Asia/Shanghai): Beijing `text-embedding-v4`, 1024 dimensions, 3 vectors, 39 input/total tokens. Related cosine similarity 0.646563; unrelated 0.201611; comparison passed. Only fixed non-private test sentences were sent. The result excludes credentials, owner workspace ID, full vectors, and personal archives. Local credentials remain in ignored owner-only `.env`.

## Evidence limits

This proves configured endpoint authentication, validated vectors/usage, and one fixed semantic comparison. It does not prove general Chinese recall, automatic extraction, pgvector persistence, history search, budgets in the product ledger, Telegram behavior, restart/forget/restore, or deployment acceptance. The standalone invocation consumed provider quota; billed/free-quota settlement was not checked. Future acceptance must follow [Memory v2](../design/memory-v2.md).
