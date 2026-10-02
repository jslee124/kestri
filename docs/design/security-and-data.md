# Security and data design

[简体中文](security-and-data.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Status: implemented first-version boundary design; M1, M2, M3, and M4 verification is linked in [first-version acceptance](../development/first-version-acceptance.md). Exact data rules are in the [lifecycle reference](../reference/data-lifecycle.md).

## Objectives and trust boundaries

Protect the owner's existing files, credentials, personal data, and control over delegated work. Make permissions and data use understandable. Limit damage from mistakes, malicious source content, and unexpectedly expensive or long-running tasks.

The owner and explicitly configured application policy authorize operations. The model proposes tool calls; application code decides whether to execute them. Web pages, extracts, tool output, generated summaries, and inferred preferences cannot grant authority.

| Boundary | First-version policy |
| --- | --- |
| Telegram identity | Configured owner user ID and allowed private chat only |
| Trusted application | Owns credentials, authorization, scheduling, memory, and persistent state |
| Model | Receives selected context and permitted tool definitions; has no direct host or database access |
| Controlled tools | Validate arguments and scope; perform only bounded, permitted operations |
| Workspace | Dedicated research and result files, separated by task/run |
| Future code sandbox | Separate execution environment; deferred until scripts or code execution are introduced |

“Trusted application” describes a software boundary, not a guarantee that all its code is correct. Initial tools share application-process privileges; they are not independently isolated sandboxes. Arbitrary model-authored code is excluded so that privileges remain behind controlled operations.

## Local deployment and filesystem access

Run the application and PostgreSQL locally through Docker Compose. Use a non-root application user, minimal capabilities, the default seccomp profile, bounded resources, and only necessary mounts. Keep the database on an internal service network with no published database port. Do not mount the Docker daemon socket into the application.

M1 defaults to a dedicated named workspace volume and a separate database volume, exposing no existing host user directories. A dedicated host directory may later be bind-mounted as the workspace. A writable bind mount changes real host files, including deletion; it is not a disposable copy. Docker documents this behavior and supports read-only mounts. Docker Desktop itself runs its daemon in a Linux VM, but bind-mounted native files remain exposed. See [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/) and [Engine security](https://docs.docker.com/engine/security/).

Workspace operations must validate resolved paths, reject traversal and symlink escape, and bind operations to the current task/run scope. They must not overwrite or delete important originals silently. User-provided originals should be copied or accessed read-only through a later explicit import design. Broad home-directory access is outside the first version.

Database and credentials are outside model tool access. M4 managed backups use a controlled workspace directory inaccessible to UUID evidence tools. A same-volume backup is not an independent recovery boundary; manage off-device copies separately.

When arbitrary code is introduced, use a separate short-lived tool container with only task inputs and outputs. Do not provide personal databases, service credentials, host control sockets, or unrelated files. Default file-processing jobs to no network and impose process/time/output/resource quotas. VM isolation may be reconsidered for heavier untrusted execution. The sandbox broker and implementation are not selected in this baseline.

## Tool authorization and side effects

Before a tool operation, validate owner identity, active run, authorization scope, argument shape, path or URL, cancellation state, and resource limits. Tool definitions alone are not enforcement.

Explicit task creation and explicit memory writes execute with a precise acknowledgement when their targets are clear; a redundant approval is unnecessary. Ambiguous modification or deletion waits for clarification. Existing user authorization applies only within its stored scope.

Creating results inside the dedicated task workspace is permitted. Access to important originals, connected-account changes, arbitrary shell, plugins, and computer control is not exposed in the first version. Any later confirmation must bind to a specific operation and arguments; a model-generated claim of approval has no authority.

## Web access and untrusted content

Public information access uses controlled search and extraction adapters. Bound time, redirects where locally fetched, response size, and model-visible output. Accept only supported public-web URLs. Reject localhost, private/link-local addresses, metadata endpoints, embedded credentials, and unsupported schemes; local fetching must validate resolved destinations and each redirect, not only the initial string.

Provider-side extraction also needs an explicit public-URL policy. Do not assume that delegating a URL to Tavily substitutes for Kestri's policy or guarantees the provider's destination controls. The chosen adapter behavior must be tested; a future local fetcher must enforce network checks independently.

Preserve source URLs, retrieval time, available publication metadata, and truncation/failure status. Store full material separately when appropriate and expose bounded excerpts or references. Source content remains evidence, including after summarization; instructions embedded in it are not user requests.

## Personal memory

Keep personal memory separate from conversation archives, execution state, task agreements, and research evidence. Retrieval starts with structured and keyword access, a small set of applicable preferences, and task-relevant entries. Vector search is deferred until a demonstrated retrieval need exists.

Each entry records content, source message, scope, creation/update time, and active/superseded/forgotten status. Explicit writes are acknowledged with the content saved. Inferred preferences remain suggestions until accepted. Task-scoped preferences do not become global automatically. Temporary facts can expire; conflicting corrections supersede older entries.

Sensitive facts require explicit retention intent. Credentials belong in secret configuration, never personal memory. Memory cannot authorize file access, account actions, or recurring work.

Forgetting removes an entry from active retrieval and suppresses automatic re-extraction from retained source messages. Cached context and summaries carrying that entry need invalidation or regeneration. Historical copies must not silently re-enter automatic context; explicit archive inspection is a separate operation. A future explicit request may establish a new memory. Deletion markers and restore handling must be designed before deletion is claimed to be effective.

M3 implements tombstones, expiry filtering, and context-epoch invalidation: each successful memory change resets the foreground head and prevents automatic access to old replies/evidence. Explicit archive inspection remains available. This removes forgotten facts from active use; historical copies are not physically erased. M4 quarantine prevents automatic permission restoration; see the [data reference](../reference/data-lifecycle.md).

## Conversation context

One Telegram chat contains the main dialogue and background deliveries; internally they use different contexts. Assemble recent complete interactions, a rolling summary of older history, relevant memory, and selected task evidence. Reply associations allow precise retrieval of earlier task results.

Persist original messages separately before compression. LangGraph checkpoints track execution state and may contain summaries; they are not the authoritative original archive. Keep tool-call/result interactions complete when trimming. Summaries preserve goals, decisions, constraints, corrections, unresolved work, and source/artifact references, without promoting untrusted text into instructions.

Permissions, task lifecycle, and authorization live in structured records outside summaries. Compression does not create personal memory. If a summary is insufficient, retrieve retained originals or evidence; if material expired, state the gap.

The active request budget and trigger are maintained in [architecture](architecture.md). Token accounting must include prompt/tool overhead and allow output space. Automatic summarization failure needs bounded recovery; it must not result in a fabricated summary or an unbounded oversized request.

## Data processing and secrets

Local storage does not imply that all processing stays local. The chosen services receive data needed for their role:

| Service | Data crossing the boundary |
| --- | --- |
| Telegram | Conversation messages, status updates, and delivered results |
| DeepSeek official API | Assembled prompts, selected memory, conversation material, tool definitions, and relevant tool results |
| Tavily | Search queries and extraction URLs; retrieved material returns to Kestri |
| Cloudflare, only with opt-in DNS mode | Candidate public-page hostnames for DNS verification; no service credentials |

Send relevant data rather than full archives or databases. Service credentials are available only to their application adapters and must not appear in prompts, source-control files, artifacts, or logs. Avoid unrestricted HTTP tools that could export secrets or private data. No cloud tracing service is selected by default.

Provider-side retention and Telegram message deletion are separate from local deletion. Local cleanup must not be represented as guaranteed erasure of externally processed data. Review provider terms when implementing integrations; no provider privacy guarantee has been established by this design.

## Adjustable retention defaults

M4 defaults are 90 days for conversation/answer archives and 30 days each for raw evidence, detailed events, and managed backups. Active memory and nondeleted task agreements are retained separately; no pinned-result interface exists. Cleanup invalidates context and removes graph copies. Restore quarantines all imported active memories, pauses nondeleted tasks, and discards pending commands on first startup. Minimal deduplication/revocation/financial records remain. Exact interfaces, boundaries, and limits are in the [data reference](../reference/data-lifecycle.md) and [ADR-0006](../decisions/0006-conservative-data-recovery.md).

## Limits and validation

Enforce bounded calls, runtime, outputs, concurrency, and estimated spending. Check limits before new operations, and track in-flight work that may still complete or incur charges. Logs should show permitted operations, outcomes, and policy rejections without revealing secrets.

Containers, application policy, and backups address different failure modes; none establishes absolute safety. Acceptance evidence must cover both normal workflows and direct boundary attempts, including malicious page instructions, path escape, private-network requests, deletion resurrection, restarts, and uncertain delivery. See [requirements and acceptance cases](requirements.md), especially AC-01, AC-07, and AC-10 through AC-12.
