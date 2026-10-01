# M1 validation record

[简体中文](m1-validation.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-01. Status: M1 verified locally and through live services; remote CI pending. This record distinguishes observed evidence from pending work.

## Revision and environment

Work branch: `codex/m1-telegram-research`, based on `5517481`. The implementation revision will be linked after committing. Implementation/configuration SHA-256: `08a5a37b27b349c79e551314a3b6b15499ffb132ab824664908a8d0ef374924f`. Concatenate each path, NUL, file bytes, NUL for sorted recursive `src/kestri` Python and SQL files, then `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `compose.yaml`, `compose.dev.yaml`, `.env.example`, and `.github/workflows/checks.yml`, in that order. Tests and documentation are outside this fingerprint. Local environment: macOS, Python 3.14.7, uv 0.12.3, and OrbStack Docker with Linux arm64 containers. Locked core versions: LangChain 1.4.3, LangGraph 1.2.12, langchain-deepseek 1.1.1, langgraph-checkpoint-postgres 3.1.2, psycopg 3.3.6, and httpx 0.28.1.

## Controlled checks

65 tests pass with a real, isolated PostgreSQL 17 database. No tests are skipped. Ruff lint/format and strict mypy pass. The actual LangChain runtime and DeepSeek request serialization are exercised with mocked external HTTP responses.

Coverage includes owner/private-chat rejection before storage/model work; deduplication and cursor recovery; concurrent spending reservations; cancellation of an actual waiting model request while polling stays available; subsequent worker reuse; model/tool/context/time limits and provider errors; source instructions followed by a forced private-URL request; failed/truncated extraction; scoped UUID evidence and symlink/path rejection; fresh-agent checkpoint follow-up; `/new` archive preservation; saved-result retries and chunk ordering; and quarantine of uncertain sends. Full task/memory/compression/deletion cases are deferred.

Known-failure checks and a fresh-agent checkpoint test provide controlled recovery evidence. They do not establish real network-outage behavior, crash behavior at every machine instruction, or immunity to all model-level prompt injection.

## Live services and messaging

Real DeepSeek official API (`deepseek-flash`, thinking disabled) and Tavily calls completed research and a follow-up using PostgreSQL state. The first system-DNS attempt rejected all sources because the installed proxy resolved public sites to benchmark-range fake IPs. This was retained as a failed retrieval observation, not counted as research success. The opt-in Cloudflare resolver verified public records without allowing private addresses, and the repeated query retrieved source material.

The owner created a new Telegram bot through BotFather with explicit authorization. Its token is stored only in ignored local configuration. Owner identity was verified against an exact test message sent through the logged-in Telegram UI, rather than enrolling the first sender. The container received and answered that private message.

A real Telegram research request retrieved the official agents and persistence pages, preserved a failed extraction for a deliberately nonexistent page, cited the successful sources, and distinguished snippets and inference. Canonical messages, run records, usage metadata, checkpoint state, and retained source text are in private database/workspace volumes. Source links initially showed a Telegram punctuation issue; the final formatter separates each URL onto its own line.

After recreating the application container, a reply-associated follow-up used the prior committed checkpoint and identified the failed page. A fresh extraction verified three complete URL lines in the saved and delivered result. A running research request was stopped through `/stop`, with status `cancelled` and an unknown reservation retained. `/status`, `/usage`, and `/help` delivered actual control responses. [Sanitized live metadata](evidence/m1-live.json) records these four research runs without owner/chat IDs, credentials, raw reasoning, or full source text. The observed local deployment estimate was $0.1162 across 18 operations, including a separate onboarding test; this is not a provider invoice. Remote CI is pending.

## Container checks

The Compose image builds successfully on Linux arm64 with Python 3.14.7. Actual execution verified UID 10001, workspace read/write, PostgreSQL checkpoint setup, and denied writes under `/app`. The final tested image is `sha256:7c12801e8984509528e7775ab48c7e57798117c97734bf5d617f2d26dca91dbb`. The deployed app is polling the bot; the database is healthy and has no host-published port. Default mount types are named volumes, with no home directory or Docker socket mounted. Configuration sets read-only root, dropped capabilities, no-new-privileges, bounded tmpfs and CPU/memory/PID resources.

These observations cover the tested container platform. They do not establish Windows/Linux-host compatibility, an independent sandbox for each tool, or safe arbitrary code execution. No such execution capability is exposed.

## Requirement and case coverage

M1 focuses on AUTH-001, CHAT-001, CHAT-002, WEB-001, WEB-002, SEC-001, SEC-002, DATA-001, OPS-001, and OPS-002. AC-01 and AC-02 are verified by combining controlled rejection/boundary checks with the actual owner research, failed-source, follow-up, and messaging observations above. Controlled evidence covers foreground portions of AC-05; inbox, context, result, retry, and uncertainty portions of AC-07; reply/checkpoint portions of AC-09; research-tool boundaries in AC-10; and current limits/reservations in AC-12. Those full cases remain unverified because later milestone behavior is absent.

## Limits and remaining acceptance

M1 has no recurring tasks, personal memory, compression, retention enforcement, backup/restore, export, or resend reconciliation. `/new` clears active context, not retained data. Budgets use configured estimates and reservations, not provider-side hard billing caps. Cancellation cannot revoke already-submitted external work. URL checks govern admission to Tavily, not the provider's remote redirect/network behavior.

Keep API keys, bot tokens, owner/chat IDs, database passwords, raw reasoning, and unnecessary private content out of public evidence. Test source material remains local. Remote CI and a linked implementation revision will be added after publication; later milestone acceptance stays explicitly pending. The broader original research ran before the final formatting/shutdown fixes; the follow-up and new extraction observed the formatting update. Final controlled tests cover shutdown propagation.
