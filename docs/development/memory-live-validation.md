# Isolated Memory v2 live validation

[简体中文](memory-live-validation.zh-CN.md) · [Documentation](../README.md)

## Environment and boundaries

On 2026-10-02, current feature-worktree Python ran against disposable PostgreSQL 17 with pgvector 0.8.7 and temporary workspaces. Chrome's logged-in Telegram session sent synthetic messages to the existing owner-only bot. The original app poller was paused only after confirming zero queued/running work, pending deliveries and active recurring tasks; it was restarted afterward and its healthcheck passed. The production database was not migrated; no test messages entered its archive. Local backup/screenshots are not committed. The original bot still runs its previous image; this is isolated acceptance, not persistent deployment.

[Sanitized evidence](evidence/memory-v2-live.json) records the baseline commit, a hash of the exercised Python/SQL source, fixed thresholds, scoped database counts, usage and actual checkpoint tool names. Credentials, owner IDs, bot IDs, private archives, endpoints and raw vectors are omitted. The modified worktree was exercised before the commit; the source hash identifies those files separately from the baseline SHA.

## Verified workflow

Natural chat about a synthetic mild-food preference created an `auto_direct` active fact without `/remember`; fact and history vectors were written. After `/new`, a paraphrased query returned that preference; real `memory_query` and `memory_select` usage was recorded. After turning learning off, restarting Python retained fact recall. `/forget` removed the fact vector and reset context; the next query answered that it did not know.

A synthetic project decision was searched after a new context. Persisted tool messages confirm two `search_history` calls and one `read_history_segment`. The answer quoted the complete owner message, separated the assistant's acknowledgment and included source IDs and bounded coverage. This proves that workflow, not broad historical recall quality.

The stopped-source schema 7 backup restored through the CLI into a new empty database/workspace. Three active project facts became quarantined, the forgotten fact stayed forgotten, all three memory switches were disabled, five history jobs were cancelled, and both vector tables were empty. Starting the restored bot delivered a restore notice; a subsequent project query abstained. No imported execution or delivery replay occurred.

## Failures and implemented response

The first food source failed quote validation twice, the second attempt being a manual isolated diagnostic re-probe. Exact whole-message Unicode anchors were then supplied to the extractor; validation still checks eligible fresh owner identity, exact quote/offset and current versions. A new preference succeeded. The project source first failed; one manual re-probe succeeded. These failures are retained in evidence, not counted as first-attempt successes.

Final code records only whitelisted static failure reasons, separating unknown ID, ineligible source, quote, span, offset and secret failures. Malformed ID/quote/span/offset annotations may regenerate under the existing three-attempt cap and 5/30-second delays. Consent, source eligibility, secret and target-policy failures remain terminal. Controlled tests check annotation retry exhaustion and absence of partial publication; live retry exhaustion was not exercised. These changes reduce opaque failures; they do not prove extraction reliability gates.

Source ledger total was 10,530 micro-USD. Restore imported that historical ledger, then added 360 micro-USD for the final query: total new live workflow cost estimate **USD 0.010890**, rather than double-counting imported usage. This excludes the separate embedding corpus evaluation. Configured estimates are not provider invoices.

## Acceptance still outstanding

Full extraction precision/recall, final selector/injection quality, independent labels, and historical JSON threshold calibration remain outstanding. See [candidate evaluation](memory-evaluation.md) and [progress](memory-v2-progress.md). Existing-volume vector upgrade and persistent production deployment were not performed. Local checks: pgvector **241 passed**; ordinary PostgreSQL **213 passed, 28 skipped**; Ruff, mypy, 98 bilingual documents, SQL readability guard and wheel/sdist passed.
