# Beijing embedding connection

[简体中文](embedding.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. Status: implemented standalone provider adapter and live smoke command. This does not enable automatic memory, create pgvector tables, change Compose/database volumes, or run embeddings during Telegram chats. Planned integration is specified in [Memory v2](../design/memory-v2.md).

## Configure locally

Create an independent key in the [Beijing API key console](https://bailian.console.aliyun.com/cn-beijing/model/settings/api-key). Select China North 2 (Beijing) and record the key's workspace ID. Default workspace is suitable for personal use; custom model permissions must include `text-embedding-v4`. Keys and endpoints must use the same region. Copy credentials into the ignored local `.env`, not documentation, source, logs, or chat messages.

```dotenv
DASHSCOPE_API_KEY=YOUR_LOCAL_KEY
KESTRI_EMBEDDING_BASE_URL=https://YOUR_WORKSPACE_ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
KESTRI_EMBEDDING_MODEL=text-embedding-v4
KESTRI_EMBEDDING_DIMENSIONS=1024
KESTRI_EMBEDDING_TIMEOUT_SECONDS=20
KESTRI_EMBEDDING_EVIDENCE_DIR=.kestri/evidence
```

Replace the workspace placeholder with the real ID. `.env.example` contains placeholders only. Preserve the existing DeepSeek chat key/model. The connection uses plain HTTP through httpx, not the OpenAI service, and needs no extra SDK or local model download. The owner-specific endpoint and key are stored only locally. Restrict `.env` permissions to its owner (`chmod 600 .env`). If a key has been shared in a chat or screenshot, rotate it in the console and replace the local value; code cannot remove upstream chat copies.

## Supported configuration

`EmbeddingSettings` reads environment and current-directory `.env` independently of chat/database credentials. Missing or invalid settings exit 2 without provider access. No `KESTRI_EMBEDDING_PROVIDER` setting is needed: this adapter is fixed to Beijing DashScope.

| Variable | Default / validation |
| --- | --- |
| `DASHSCOPE_API_KEY` | Required nonblank SecretStr, excluded from repr |
| `KESTRI_EMBEDDING_BASE_URL` | Required HTTPS Beijing workspace URL ending `/compatible-mode/v1`; no userinfo, query, fragment or custom port except 443 |
| `KESTRI_EMBEDDING_MODEL` | `text-embedding-v4`; other models rejected |
| `KESTRI_EMBEDDING_DIMENSIONS` | 1024; supports 64/128/256/512/768/1024/1536/2048 |
| `KESTRI_EMBEDDING_TIMEOUT_SECONDS` | 20; >0 and ≤60 seconds; HTTP phase timeout, not total workflow deadline |
| `KESTRI_EMBEDDING_EVIDENCE_DIR` | `.kestri/evidence`; relative to working directory |

The configured optional DashScope secret also joins the Telegram/data redaction set. This is independent of enabling embedding calls in the bot. Secret redaction does not encrypt archives or files. Numeric dimensions are parsed from environment strings before validating the permitted values.

## Adapter contract

[EmbeddingClient](../../src/kestri/embedding.py) posts to `<base_url>/embeddings` with bearer authentication, model, string-list input, dimensions, and `encoding_format=float`. No redirects or implicit retries. A caller supplies and owns an AsyncClient with an appropriate timeout; the smoke configures it explicitly. At most 10 nonblank inputs, each at most 8192 UTF-8 bytes, are admitted before HTTP. This byte bound is a conservative application limit, not the provider's 8192-token limit. Inputs containing the configured embedding key are rejected. Upstream automatic-memory code must apply broader provenance/secret rules before using the adapter.

Response body is capped at 2000000 bytes. Require expected model, exactly one item per input, unique indices covering the batch, configured dimension, finite numeric values excluding booleans, finite nonzero norms, and nonnegative integer usage with total ≥ input tokens. Reorder results by input index. Return immutable vector tuples and input/total tokens. Errors use safe categories; HTTP error bodies and transport details are not included in CLI output. Validation happens before vectors are used or persisted.

## Run the live check

```sh
uv run kestri embedding-smoke
```

One request encodes three fixed non-private texts: a project/job goal, its paraphrase, and an unrelated dinner sentence. No arbitrary prompt flag, owner archive read, database connection, Telegram send, or vector persistence. The check verifies valid vectors and related cosine similarity exceeding unrelated similarity. It writes JSON evidence with UTC timestamp, provider/region/model/dimensions, request/vector counts, usage, similarities and pass status. It excludes keys, workspace URL, input text and full vectors. This directory is ignored by Git.

Exit 0 means this limited comparison passed; exit 1 means provider/validation/evidence failure or comparison failure; exit 2 means config/argument error; interruption exits 130. Unknown provider usage or failure does not trigger an automatic retry. This standalone check consumes service credits but does not use the product's PostgreSQL fee ledger. [Validation evidence](../development/embedding-validation.md) distinguishes this connection check from future recall quality.

## Storage and next implementation

Vectors are numerical indexes, not replacements for original memory text. Proposed storage is PostgreSQL with pgvector `vector(1024)`, joined to authoritative facts using content revision/hash and embedding-space version. Install the extension server-side before SQL activation; the current `postgres:17-alpine` image is unchanged. Start with exact cosine search, not an unmeasured approximate index. Separate model generations cannot be mixed even with the same dimension. Rebuild on model/recipe changes; prevent stale jobs from publishing superseded vectors. No vector table or application retrieval path is implemented by this connection increment.

## Official sources and pricing

Verified 2026-10-02 against [API key instructions](https://help.aliyun.com/zh/model-studio/get-api-key), [embedding API](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api/), [domestic prices](https://help.aliyun.com/zh/model-studio/model-pricing), and [pgvector](https://github.com/pgvector/pgvector). Beijing `text-embedding-v4` lists 0.5 CNY per million input tokens; account free-quota eligibility/expiry depends on the console. Extraction and candidate selection use a chat model and incur separate costs. Provider prices and access can change; current configuration does not hard-code a currency conversion into the product ledger.
