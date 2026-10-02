# Chinese memory candidate evaluation

[简体中文](memory-evaluation.zh-CN.md) · [Documentation](../README.md)

Current status (2026-10-02): the [completion record](../development/memory-v2-completion.md) supersedes earlier pending/deferred statements below. Natural controls, change notices, extraction/selection/history-answer synthetic evaluation and history calibration are implemented. Independent human and longitudinal quality are unmeasured.

## Corpus and scope

The [versioned corpus](../../evals/memory/chinese-retrieval-v1.json) has 24 synthetic eligible personal facts and 120 hand-labeled queries: 96 positive and 24 negative. Categories cover paraphrases, references to the user's habits, remembered project decisions, changed preferences, temporary emotions, hypotheses, quotations and unrelated questions. Labels have one author and no independent review. These are candidate-ranking labels, not extraction labels: quoted and hypothetical messages must not become facts, but this runner does not execute the extractor. The reference category does not test multi-turn anaphora resolution. Changed preferences are single current records containing before/after wording; database supersession is tested separately.

Development and holdout each contain 48 positive labels and 12 negative queries. Queries are split, but the same facts appear in both partitions; this is an initial query holdout, not an independent user/domain holdout. Each positive has one relevant ID. Empty labels mean abstain. There are no owner messages, database credentials, endpoint workspace identifiers or raw vectors in the checked-in corpus or reports.

## Runner and scoring

Run from the repository with the development environment:

```sh
.venv/bin/python scripts/evaluate_memory.py --output /private/tmp/memory-lexical.json
.venv/bin/python scripts/evaluate_memory.py --live --output /private/tmp/memory-embedding.json
```

Offline mode loads no provider settings. Live mode loads the existing ignored embedding configuration and sends only the fixed synthetic corpus, in batches of at most ten, with no automatic retries. The preflight UTF-8 byte estimate at fixed 0.5 CNY/million and 0.15 USD/CNY must fit `--max-cost-usd` (default and maximum USD 0.02). This is a standalone evaluation, outside the product ledger; unknown submitted failures may still incur costs. It does not poll Telegram or access a database. Only text-embedding-v4 at 1024 dimensions is admitted.

Scorer `eligible-fact-candidates-recall8-v1` uses production lexical ranking and reciprocal-rank fusion, exact cosine, twenty dense candidates and eight final candidates. Recall divides retrieved relevant IDs by the number of relevant labels. False candidate rate divides negative queries returning any candidate by the number of negative queries. It is **not false injection rate**: the production fact selector, always-present communication preferences and final answer are outside this scoring scope. History has its own full-message JSON recipe and five-result interface.

Thresholds 0.20–0.80 in increments of 0.05 are fixed before evaluation. Only development dense results choose the initial recommendation: require Recall@8 ≥90%, minimize false candidate rate, then prefer the highest tied threshold. Holdout scores cannot choose the threshold. Reports retain corpus hash, labels version, scorer version, model/space, denominators and per-query similarities; the tests verify denominator and holdout isolation behavior.

## Collected results

The [offline report](evidence/memory-lexical-v1.json) and [live embedding report](evidence/memory-embedding-v1.json) were collected on 2026-10-02. The retained live run submitted 15 requests, 144 vectors and 1512 input tokens; estimated cost USD 0.0001134 at the stated rates. Two complete collections were performed during implementation: 30 requests and 3024 input tokens total, estimated USD 0.0002268. These estimates are not invoices or quota settlement. Category annotations were corrected after collection; query texts and relevant IDs were unchanged, as recorded in the reports.

| Method and threshold | Development recall | Holdout recall | Development false candidates | Holdout false candidates |
| --- | --- | --- | --- | --- |
| Lexical | 34/48 | 41/48 | 0/12 | 0/12 |
| Dense, 0.30 | 47/48 | 48/48 | 9/12 | 9/12 |
| Dense, 0.50 | 46/48 | 47/48 | 1/12 | 0/12 |
| Hybrid, 0.50 | 46/48 | 48/48 | 1/12 | 0/12 |

The fact default changes to **0.50**, a bounded initial calibration for this configured fact recipe. An explicit environment override still wins. Historical recall originally used a provisional 0.30; the independently calibrated `KESTRI_HISTORY_DENSE_MIN_SIMILARITY` now defaults to 0.60. Neither threshold is a universal semantic relevance rule.

## Evidence boundary

Candidate ranking alone does not measure extraction or final injection. The final collection below adds those stages. Independent human/domain labels, harder multi-turn cases and longitudinal user quality remain unmeasured.

## Final quality collection

The candidate results above describe the earlier increment. The [completion record](memory-v2-completion.md) now records actual extraction, final related-fact assembly, full-turn history calibration and registered-tool historical answers. History now defaults to 0.60. Synthetic regression and isolated Telegram acceptance have passed; independent labels and long-term personal-chat quality remain unmeasured. See the deployment procedure for the running version.
