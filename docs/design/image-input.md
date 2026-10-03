# Image input

[简体中文](image-input.zh-CN.md) · [Documentation](../README.md)

## Scope and experience

Support Telegram photos, image documents (JPEG, PNG, WebP), captions, albums, and
follow-up questions such as “compare images 1 and 2”. Responses remain text. Albums
produce one research run and one acknowledgement. Captions are research input, never
memory or task control commands. No animation, PDF, image search, or image generation.

## Durable reception

Keep owner/private-chat authorization before any download. Store every update in the
existing inbox transaction. Group album members by chat and `media_group_id`; append
only while the run is queued and collection has not closed. Delay admission until two
seconds after the latest member, with a ten-second collection ceiling. This is a heuristic:
Telegram supplies no album-complete signal. Late members get a resend notice and cannot
silently start another run. A restart retains queued collection and inbox deduplication.
Number images within each message by Telegram message ID, not arrival order.
Foreground text arriving behind a collecting album waits for that album. Use one suitable photo size,
not every thumbnail version. New album captions are combined in message order.

## Attachments and model input

Migration 11 adds `runs.media_group_id` and `image_inputs`, containing UUID, run/chat,
Telegram message/file IDs, caption, status, detected MIME, dimensions, byte size, hash,
and creation time. The file IDs are private transport metadata, never model input.
Download at execution time through `getFile`, bounded streaming, no redirects, and a
validated Telegram-relative path. Never forward a token-bearing download URL.

Use private UUID-named `.image` files within the existing no-follow workspace boundary.
Decode and verify actual pixels with Pillow; accept only static JPEG/PNG/WebP. Admit
at most 10 images, 10 MiB per file, 20 MiB per model request, 8192 pixels per side,
and 32 million pixels per image. These limits apply across retained image context.
Unsupported, missing, or failed images stop the turn with a concrete resend notice;
never answer as if every image had been read.

Checkpoints store text plus `image_refs` metadata, not image bytes. Model middleware
resolves authorized references into ephemeral `image_url` data blocks. Verify the
locked DeepSeek serializer with an offline HTTP transport. The configured model must
support vision; the default `deepseek-flash` does according to the official documentation.
Do not silently switch providers. Image content is untrusted evidence, not permission.

## Context, budget, and memory

Count each image conservatively as 1024 input tokens plus ordinary text/framing, reserve
before billable calls, and settle from actual provider usage. This estimate is specific
to the documented DeepSeek Flash image contract. Summaries consume prior dialogue and
attachment references, not base64 text; retain references for subsequent visual inspection.
If active context exceeds attachment limits, ask the owner to use `/new`.
Automatic memory extraction must not treat image interpretation as an owner statement.
Do not enqueue image captions as automatic personal-memory sources in this version.

## Lifecycle and validation

Backup schema 9 includes attachment records and verified base64 bytes; export includes
the same image bytes so exported references remain useful. Existing bundle size limits
still apply. Restore accepts schemas 4–9, supplies missing legacy columns, validates
image hashes/metadata and owner links before writing, and retains conservative quarantine.
Restore pending downloads as expired: no automatic Telegram re-download after restore.
Retention uses evidence retention or earlier archive expiry; mark files pending cleanup
before unlinking so a crash can resume deletion. Clear image references in checkpoints
when retained files expire. Erase removes transport identifiers as well as bytes.

Acceptance covers authorization; albums across polling batches; duplicates, late members,
ordering and restart; download/format/size failures; actual outgoing multi-image payloads;
follow-up/checkpoint/summary boundaries; budget; backup/export/restore/cleanup. Run Ruff,
mypy, offline and isolated PostgreSQL tests, bilingual docs and SQL checks, controls
evaluation, and package build. Live Telegram/provider acceptance is separate evidence.

## Sources

- [DeepSeek vision](https://api-docs.deepseek.com/guides/vision/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [LangChain messages](https://docs.langchain.com/oss/python/langchain/messages)

[Local validation record](../development/image-input-validation.md).
