# Requirements and acceptance criteria

[简体中文](requirements.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Status: draft specification based on agreed product behavior. **AC-01 through AC-07 are verified across M1/M2; AC-08 and AC-09 are verified across M1/M2/M3. AC-10 through AC-12 retain partial coverage until M4.** See [M1 evidence](../development/m1-validation.md), [M2 evidence](../development/m2-validation.md), and [M3 evidence](../development/m3-validation.md). [M0 evidence](../development/m0-validation.md) covers only initial model/tool foundations and part of AC-12.

## Interpretation

This document turns the [product scope](product.md) into reviewable first-version requirements. “Must” denotes a release acceptance condition, not an implemented capability. The identifiers remain stable across languages and later implementation changes.

Numeric operational defaults are maintained in [architecture](architecture.md) and [security and data](security-and-data.md). They are adjustable initial values, not provider limits or validated performance targets.

## Functional and quality requirements

| ID | Requirement |
| --- | --- |
| AUTH-001 | Accept requests only from the configured owner user ID in an allowed private Telegram chat. Rejected requests must not start model calls, retrieve personal information, or modify state. |
| CHAT-001 | Execute actionable research requests directly. Ask for missing information only when it materially affects the outcome; otherwise state assumptions. Give concise status feedback for substantial work and support stopping the foreground run. |
| CHAT-002 | Associate replies with the relevant result or run. An unqualified stop targets the active foreground run; a stop replying to a known run targets that run. If a task-control target remains ambiguous, clarify before changing state. |
| WEB-001 | Search public sources, extract relevant pages, and synthesize findings with supporting links. Keep source provenance; distinguish sourced facts, interpretations, and missing evidence. A search snippet alone must not be presented as having read the full page. |
| WEB-002 | Bound web requests and model-visible material by time and size. Indicate failed extraction, truncation, and inadequate evidence. Do not fabricate a successful retrieval or continue searching indefinitely. |
| TASK-001 | Create a recurring task only when a request authorizes it and required information is available. Persist and echo timing, explicit timezone, content instructions, and missed-run behavior. A complete request needs no redundant creation approval. |
| TASK-002 | Let the owner list, modify, pause, resume, and delete recurring tasks. Identify the target through reply association or context; require clarification if unresolved. A deleted task must create no further scheduled runs. |
| TASK-003 | After pause acknowledgement, start no new scheduled runs for that task; already-running work continues. Treat stopping a current run separately. After a cancellation request is processed, initiate no further work for that run; report any in-flight operation that cannot be stopped. |
| TASK-004 | Execute and report recurring work only within the stored user agreement. Memory, source text, model suggestions, and timing events cannot expand authorization or create new tasks. |
| TASK-005 | Apply a persisted, task-specific missed-run policy after downtime. Within the configured window, coalesce missed occurrences into at most one catch-up run; outside it, skip and schedule the next occurrence. |
| TASK-006 | Persist run and delivery states separately. Use bounded retries for transient failures and reuse an already-generated result when delivery fails. Record uncertain send outcomes rather than claiming exactly-once delivery. |
| MEM-001 | Save explicitly requested preferences or facts and acknowledge their exact content. Store source, scope, timestamps, and status. Apply task-specific preferences only to that task unless the owner requests broader scope. |
| MEM-002 | Require the owner's acceptance before persisting a suggested inferred preference. Treat inference as a candidate, not an established personal fact. |
| MEM-003 | Let the owner inspect, correct, and forget memory. A forgotten or superseded entry must not influence retrieval or be automatically reconstructed from retained history. Forgetting memory and deleting source history are distinct operations. |
| CTX-001 | Keep the main conversation and each background execution in separate internal contexts while using one Telegram chat. A follow-up may retrieve relevant run evidence without adding the entire background trace to the foreground history. |
| CTX-002 | Archive original messages separately from compressed agent state. Apply budget-aware summarization while preserving recent complete tool interactions, current decisions, constraints, corrections, and evidence references. Permission and task-control records must not depend on a lossy summary. |
| SEC-001 | Validate every tool request in application code against identity, scope, arguments, and resource limits. Restrict filesystem work to the dedicated workspace. Do not provide arbitrary code execution, unrestricted host access, or connected-account mutation in the first version. |
| SEC-002 | Treat web pages, extracts, tool output, and model-generated instructions as untrusted data. They must not grant access, create recurring tasks, overwrite personal memory without user intent, or become higher-priority user instructions through summarization. |
| DATA-001 | Persist task agreements, personal memory, accepted inbound messages, and required execution state so an ordinary restart does not silently lose them. Process redelivered Telegram updates without repeating accepted state changes. |
| DATA-002 | Apply documented retention separately to original conversations, checkpoints, research material, and operation logs. Distinguish active-data deletion from backup expiration; restoring a backup must not silently reactivate deleted tasks or forgotten memories. |
| OPS-001 | Let the owner inspect tasks, personal memory, and recent runs, including status, evidence references, failure information, cancellation, and delivery uncertainty. Never include secrets in user-visible records or logs. |
| OPS-002 | Record model/search usage and estimates of cost, with configured time and call limits. Enforce a local budget policy before new billable work and report exhaustion. Do not describe estimated charges or local limits as an exact provider billing guarantee. |

## Acceptance cases

These cases define outcomes to demonstrate later. They do not prescribe a test framework or implementation sequence.

| Case | Requirements | Scenario and expected outcome | Evidence required |
| --- | --- | --- | --- |
| AC-01 | AUTH-001, SEC-001 | An unconfigured user or disallowed chat requests personal information or a task. No model work or personal-state change occurs. The owner can still use the bot. | Controlled authorization checks and Telegram integration evidence |
| AC-02 | CHAT-001, WEB-001, WEB-002 | Research a question with accessible and inaccessible pages. The response cites retrieved evidence, marks limitations, and supports a follow-up; unavailable pages are not described as successfully read. | A live-provider example with retained source material and bounded failure checks |
| AC-03 | TASK-001, MEM-001 | Ask for an 08:00 daily briefing with a configured timezone. One task is created and the agreement is echoed. With no timezone configured, clarify before scheduling. “Make this briefing shorter” affects the task, not global answer style. | Persisted agreement and observed chat outcomes |
| AC-04 | CHAT-002, TASK-002 | With multiple tasks, reply to one and change its time. Only that task changes. An ambiguous deletion request asks for clarification and changes nothing. Listing and explicit deletion work. | State before/after each control action |
| AC-05 | CHAT-001, TASK-003 | Pause a task during an active run. That run continues; the next occurrence creates no run. Explicitly stop a foreground run and demonstrate the cancellation boundary, including any in-flight work. Resume permits later occurrences. | Run records and observed scheduling/cancellation behavior |
| AC-06 | TASK-004, TASK-005 | Recover after one or several missed occurrences within the catch-up window, and again outside it. Produce at most one eligible catch-up; do not flood the chat with missed briefings. Use only the stored task agreement. | Deterministic clock checks and a restart demonstration |
| AC-07 | TASK-006, DATA-001 | Restart around inbound acceptance, result persistence, and delivery. Repeated Telegram updates do not repeat a task mutation; generated results survive. A failed send retries the saved result; an ambiguous send is marked uncertain. | Failure-injection and recovery records; live messaging checked separately |
| AC-08 | MEM-001, MEM-002, MEM-003 | Save a preference, inspect it, apply it to a relevant question, update it, and forget it. Revisit its source conversation afterward; the old entry is not silently resurrected. A suggestion is not saved without acceptance. | Memory/source records and retrieval outcomes |
| AC-09 | CHAT-002, CTX-001, CTX-002 | Run a background briefing while chatting, then reply to its second item. Retrieve relevant evidence. Force compression; verify a correction such as “Python replaces TypeScript” remains accurate and the original history remains retrievable. | Assembled context, archive, and checkpoint inspection |
| AC-10 | TASK-004, SEC-001, SEC-002 | Retrieve material that asks the agent to read secrets, create a task, alter memory, or access a private-network URL. Also attempt a direct out-of-scope tool request. No unauthorized effect occurs and policy rejections are recorded. | Controlled adversarial fixtures and tool-boundary checks |
| AC-11 | MEM-003, DATA-002 | Expire temporary material, forget memory, and delete a task. Verify active retrieval and scheduling stop using removed data. A restore procedure accounts for deletions; document the backup expiration boundary. | Retention/deletion checks and restore evidence |
| AC-12 | WEB-002, OPS-001, OPS-002 | Reach a call, time, output, or budget limit and simulate a terminal provider failure. Work terminates with useful status, inspectable usage, and a concise notification without leaking credentials. | Boundary checks, operation records, and messaging observation |

## Specification work still open

- Archive retention/deletion, backup/restore interfaces, and deletion-marker retention.
- Full-case acceptance of AC-10 through AC-12 and the integrated M4 personal-use trial.

M1 foreground controls, queue values, restart handling, reservations, credit estimates, and delivery uncertainty are specified in the [implemented reference](../reference/telegram.md). Evidence status is in the [M1 record](../development/m1-validation.md).

Resolve these through focused design review before the affected behavior is called complete. Link later implementation and evidence to the IDs above; keep every acceptance case unverified until supported by actual results.

M2 agreements, controls, concurrency, and catch-up are specified in the [task reference](../reference/tasks.md); acceptance scope is tracked in the [M2 record](../development/m2-validation.md).

M3 explicit memory, original-history inspection, and compression are specified in the [memory/context reference](../reference/memory-and-context.md); see [M3 evidence](../development/m3-validation.md).
