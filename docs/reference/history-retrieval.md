# Bounded chat history tools

[简体中文](history-retrieval.zh-CN.md) · [Docs](../README.md)

## Availability and consent

On the Memory v2 feature branch, foreground research registers `search_history` and `read_history_segment` only while both `/memory auto on` and `/memory use on` are active. This first increment deliberately couples history availability to extraction consent. Turning auto off pauses history tools but retains use of existing personal facts. Changing auto on/off resets the foreground head and advances the context epoch, preventing previous history tool messages from carrying into a new consent period. Re-enabling auto sets a fresh archive watermark; no old-history backfill occurs. Restore disables auto/use, so restored archives cannot be searched automatically.

The enabling receipt discloses that later chats can be sent to DeepSeek on demand for historical questions. Local search/read do not call a provider or create usage reservations; subsequent model calls and context summaries still use the existing spending ledger. Retrieved text can persist as tool messages in the run's graph checkpoint and appear in summaries/answers. This differs from ephemeral personal-fact system injection. Epoch invalidation, source retention cleanup, and checkpoint cleanup apply; revocation cannot recall requests already submitted to a provider. `/history` remains an independent explicit owner-only archive viewer.

## Tool contract

`search_history(query, before?, after?, limit=5)` rejects unknown fields, empty/blank queries, queries over 500 characters, and limits outside 1–5. Optional dates are timezone-aware ISO-8601 strings, at most 40 characters; `after` is inclusive and `before` exclusive, with `after < before`. Owner, run, and task identity come from application dependencies, never model arguments.

Search considers the newest at most 200 eligible owner turns in the requested time window, strictly before the current run. Eligibility requires that owner's direct inbound messages, foreground runs whose history is not expired, source IDs above both activation and forgetting floors, and global/current-task scope. Forwarded, legacy, external, command/control, background, and current-run sources are excluded. Assistant context may accompany an eligible owner turn only from that same run. A turn has at most 12 complete messages and 8000 content characters; individual sources over 24000 UTF-8 bytes or turns exceeding limits are skipped entirely. Known configured secrets and the shared credential-pattern filter cause a turn to be skipped; this is not a perfect sensitive-information classifier.

Ranking reuses Chinese overlapping bigrams and ASCII terms with positive-match IDF weights. This increment is **lexical**, has no historical embeddings or hybrid history search, and never pads zero matches with recent turns. Results explicitly disclose bounded coverage: an empty result does not establish absence in the complete archive. Up to five results contain a 400-character owner snippet with a truncation flag, date, message count, and source handle. A hit can originate in an attributed assistant reply; the owner snippet is not claimed to prove every matching term.

`read_history_segment(segment_id)` requires a SHA-256 handle issued by search in the **same run**. The handle fingerprints ordered message IDs, Telegram IDs, roles, UTC dates, and full content. Application memory holds the handle, owner source ID, and consent version; this is a change detector, not an authorization token or portable archive identifier. Read reloads the complete turn, checks scope/floors/consent/current epoch/history expiry, verifies the fingerprint, and rechecks settings before returning. Alteration, source removal, a different run, or consent change denies access. Complete read results label owner statements and assistant proposals separately and never silently truncate content.

## Bounds and lifecycle

Both tools count toward the existing run-wide tool-call cap and run timeout. JSON output must fit `tool_output_chars`; read rejects overflow rather than clipping a historical claim or returning broken JSON. Search admits fewer snippets when the configured limit is small. Input schema and returned messages are included in the normal next-model admission check. History does not create facts, grant task authorization, or expose arbitrary file/owner access. The system prompt explicitly treats historical text as untrusted dated evidence.

No tables, migrations, derived text copies, or backup schema changes are added. Source retention removes access; broad epoch reset prevents stale graph reuse. Forgetting advances the existing automatic history floor. Handles are discarded when a run ends or restarts; a retried run must search again. Search rechecks selected sources before issuing handles, and read validates source hashes. Local database reads cannot retract text already returned to a caller; normal epoch/activity checks also run before subsequent model requests and result publication.

## Validation and remaining work

[History tests](../../tests/history/test_history_integration.py) cover schemas/time/turn bounds, default-off consent, activation cutoff, zero matches, search limits, source hashes/removal, foreign/forwarded source denial, expired runs, use/auto revocation, races, oversized/credential turns, output rejection, role attribution, and actual framework tool routing with HTTP mocks. These are controlled checks, not live chat quality acceptance.

Remaining Memory v2 history work: persistent eligible segment indexing and hybrid retrieval, Chinese labeled evaluation including paraphrases and historical decisions, and isolated live provider/Telegram restart/forget/restore acceptance. The lexical tools do not satisfy the complete hybrid-history specification. See [progress](../development/memory-v2-progress.md) and [design](../design/memory-v2.md).
