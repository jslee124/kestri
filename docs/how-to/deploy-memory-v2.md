# Deploy Memory v2 locally

[简体中文](deploy-memory-v2.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02. This guide also records the completed local deployment. Full semantic quality acceptance remains pending.

## Current deployment

Source `b1d7bf27450fde2f595db85a2374d12fb5884824` is running in the existing `kestri-app-1`. Its installed Python/SQL hashes match that revision. PostgreSQL retained `kestri_database`, the same PostgreSQL 17 Alpine base and data directory; the optional overlay adds pgvector 0.8.7. The database advanced from migration 4 to 8. Immediately after migration, the original 27 runs and 113 messages were unchanged. The original workspace volume is retained.

Both containers are healthy. Telegram `/memory` responded with **auto off, use on, semantic off**; after a deliberate app restart, `/memory changes` responded with no background jobs or failures. No production content was extracted or embedded by these checks. [Sanitized evidence](../development/evidence/memory-v2-deployment.json) records image digests and the verification boundary. Earlier [isolated live validation](../development/memory-live-validation.md) covers synthetic semantic workflows separately. The branch was not merged to main.

## Operate this installation

Run commands from the repository root:

```sh
docker compose -f compose.yaml -f compose.vector.yaml ps
docker compose -f compose.yaml -f compose.vector.yaml exec app /app/.venv/bin/kestri data status
docker compose -f compose.yaml -f compose.vector.yaml restart app
```

Keep **both** Compose files on future build/up commands, so PostgreSQL keeps its extension-enabled image. `docker compose up` with only the base file can replace it. Do not use `down -v`. Docker must be running; `unless-stopped` does not wake a sleeping computer.

Automatic learning and semantic recall are independent owner controls. To use them, the owner sends `/memory auto on` and `/memory semantic on` in Telegram. Auto starts from a new watermark and does not extract old chats; semantic may index already authorized active facts. Data destinations and budgets are specified in [semantic memory](../reference/semantic-memory.md). This deployment did not change those controls on the owner's behalf.

## Upgrade with recoverable snapshots

Build before stopping the poller:

```sh
docker compose -f compose.yaml -f compose.vector.yaml build app postgres
docker compose -f compose.yaml -f compose.vector.yaml stop app
```

Before running a newer application command, take a full PostgreSQL dump and workspace archive. `data backup` calls `Store.open()` and can apply migrations; it is not a substitute for a pre-migration snapshot. Keep the old app image under a separate tag before building. Private snapshots belong in the ignored `.kestri/deployment/` directory with directory mode `0700` and file mode `0600`, outside published evidence.

The completed deployment retained `database-before.dump`, `workspace-before.tar.gz`, a post-migration schema 7 logical bundle, private checksums and a private `rollback.compose.yaml` under `.kestri/deployment/2026-10-02-memory-v2/`. The dump was restored with `pg_restore --exit-on-error` in a separate disposable database; migration/run/message counts matched. Every archived workspace file was readable. The disposable check container and its anonymous volume were removed.

After checking snapshots, recreate PostgreSQL with the overlay. A new-image `data backup` initializes schema without starting Telegram or model work; then start the app:

```sh
docker compose -f compose.yaml -f compose.vector.yaml up -d --no-build postgres
docker compose -f compose.yaml -f compose.vector.yaml run --rm --no-deps app data backup
docker compose -f compose.yaml -f compose.vector.yaml up -d --no-build app
```

Check migration version, vector tables, preserved counts, `/memory`, health and an app restart. Do not infer model availability from the database healthcheck.

## Roll back into separate volumes

Do not run the old app or extension-free PostgreSQL image against the upgraded production database. Prefer a forward fix. If rollback is necessary, stop the current app, preserve newer data, and restore the **pre-upgrade** dump/workspace into a separate project. The retained private Compose file uses `kestri-app:rollback-pre-memory-v2`, the original PostgreSQL image, separate named volumes, the existing local credentials and the same container isolation. Its Compose configuration was validated without printing secrets.

The following is the retained rollback recipe, not an operation performed on production. Run only with empty rollback volumes, from the repository root:

```sh
docker compose -f compose.yaml -f compose.vector.yaml stop app
docker compose --env-file .env \
  -f .kestri/deployment/2026-10-02-memory-v2/rollback.compose.yaml up -d postgres
```

Wait until the separate database reports ready, then restore:

```sh
docker compose --env-file .env \
  -f .kestri/deployment/2026-10-02-memory-v2/rollback.compose.yaml \
  exec -T postgres pg_restore -U kestri -d kestri --exit-on-error \
  < .kestri/deployment/2026-10-02-memory-v2/database-before.dump

docker run --rm -i --network none \
  -v kestri-memory-v2-rollback_workspace:/target \
  --entrypoint tar postgres:17-alpine -xzf - -C /target \
  < .kestri/deployment/2026-10-02-memory-v2/workspace-before.tar.gz
```

Inspect restored records and Telegram offset/pending work before starting the rollback app with the same private Compose file. Only one poller may run. A snapshot rollback does not include conversations accepted after the snapshot and can expose pending Telegram updates again. Preserve the upgraded volumes for reconciliation; do not delete either copy. This raw-dump recovery is distinct from `kestri data restore`, which accepts logical bundles and deliberately quarantines state.

## Remaining work

Deployment is complete with opt-in controls off. Independent extraction/selection/answer scoring, historical JSON threshold calibration, ambiguous natural-language corrections and proactive memory-change notices remain. Candidate recall metrics and synthetic live workflows do not establish the full [Memory v2 quality gates](../design/memory-v2.md).
