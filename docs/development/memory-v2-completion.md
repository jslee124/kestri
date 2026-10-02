# Memory v2 completion record

[简体中文](memory-v2-completion.zh-CN.md) · [Documentation](../README.md)

## Delivered behavior

The implementation now covers opt-in automatic extraction, structured facts and candidates, durable extraction/index jobs, DashScope embeddings, PostgreSQL/pgvector storage, bounded hybrid fact selection and history search/read, memory-use control, natural-language correction/forgetting and proactive change notices. [Memory controls](../reference/memory-controls.md) describe the supported phrases and authorization boundaries. Ambiguous targets produce a bounded list without mutating memories; an explicit ID command chooses a target. Automatic additions/replacements produce one transactional outbox notice; reinforcement and candidates remain silent. Pending notices are checked against consent, epoch and current facts before sending.

Migration 9 preserves legacy LangGraph checkpoint tables by moving them from `kestri` to `public`; connections now explicitly use `search_path=public`. This makes existing checkpoint retention and invalidation operate on the actual framework tables. A conflicting pair of tables aborts rather than merging or deleting checkpoint data. Business backup schema remains 7.

## Quality evidence

The [consolidated report](evidence/memory-v2-quality.json) retains all attempts and links their individual reports. Collectors call production adapters, extractor, selector, bounded assembly and prompts against synthetic Chinese examples. Historical ranking uses complete role-attributed turn JSON. The development split independently calibrates history similarity to **0.60**; the personal-fact threshold remains **0.50**.

| Final collector | Development | Holdout |
| --- | --- | --- |
| Extraction matched active facts | 45/45 | 45/45 |
| Negative extraction cases with active facts | 0/35 | 0/35 |
| Relevant assembled related facts, recall at 8 | 46/48 | 47/48 |
| Negative queries with related injection | 0/12 | 0/12 |
| Historical correct fact plus owner citation | 20/20 | 20/20 |
| Historical missing-evidence answers | 10/10 | 10/10 |

These are single-author regression labels. Extraction corpus v2 corrected ambiguous temporary-emotion labels after inspecting v1; its reused holdout is not untouched. Selection shares fact identities between query splits, and its injection metric excludes always-present communication preferences. Historical splits use disjoint project names. Dense history recall is 20/20 in both splits, but same-topic lexical candidates still occur for all ten negative queries: retrieval alone cannot prove an answer. Final answers are separately checked for full-source reads, owner citations and abstention.

History-answer v1 used unregistered, pre-completed tool messages and is an invalid harness, retained but excluded from product claims. Version 2 registers real search/read tools and requires an issued handle before reading; its candidates are fixed, so query rewriting and database race guarantees are checked separately. All baseline/retest attempts total **843 provider requests**, estimated **USD 0.454762** at configured rates, outside the production ledger; this is not an invoice. No private owner archive was used. Independent human/domain review and longitudinal personal-chat accuracy remain unmeasured.

## Verification and deployment

Local pgvector: **259 passed**. Plain PostgreSQL: **231 passed, 28 vector-specific cases skipped**. Checks cover ambiguous targets without writes, explicit choice, hexadecimal content versus IDs, unique natural controls, durable notices, revocation, restart and checkpoint migration/collision preservation. Ruff checks/format, mypy, bilingual documentation, readable SQL and wheel/source package checks accompany this increment.

Real Chrome Telegram acceptance uses a disposable database and workspace, with only the poll offset copied from production. It observed an automatic two-fact notice, natural SQLite-to-PostgreSQL correction, ambiguous Python target suggestions without a mutation, explicit forgetting and retained state after a process restart. Production chats were not imported into the synthetic acceptance database. The final sanitized [live record](evidence/memory-v2-final-live.json) and [deployment procedure](../how-to/deploy-memory-v2.md) record runtime evidence separately from quality scores and CI.

## Reproduce

```sh
.venv/bin/python -m scripts.evaluate_memory_quality --stage extraction --output /private/tmp/extraction.json
.venv/bin/python -m scripts.evaluate_memory_quality --stage selection --output /private/tmp/selection.json
.venv/bin/python -m scripts.evaluate_memory_quality --stage history --output /private/tmp/history.json
.venv/bin/python -m scripts.evaluate_memory_quality --stage history_answer --output /private/tmp/history-answer.json
```

Each live collector sends fixed synthetic content using the ignored provider configuration and a bounded evaluation ledger. It does not poll Telegram or load private chat archives. Retained reports specify corpus hashes, scorer versions, denominators and limitations. This completes the planned implementation and internal regression acceptance; the measured synthetic results do not promise universal personal-chat accuracy.
