# Back up and restore local data

[简体中文](backup-and-restore.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02.

## Create and inspect a backup

From your configured repository, with Docker running:

```sh
docker compose stop app
docker compose run --rm --no-deps app data backup
docker compose run --rm --no-deps app data status
docker compose start app
```

The backup command prints a private `/workspace/backups/UUID.json` path. Record it locally. It shares the application workspace volume; a same-disk backup does not protect against disk loss. For an off-device copy, use your trusted private transfer/storage workflow and preserve restricted access. Never commit the bundle or upload it with public acceptance evidence. To copy a known path out of the existing app container:

```sh
mkdir -p .kestri/backups
chmod 700 .kestri/backups
docker cp kestri-app-1:/workspace/backups/UUID.json .kestri/backups/UUID.json
chmod 600 .kestri/backups/UUID.json
```

Substitute the exact printed UUID. Host copies are not automatically pruned. For a record-only export, while stopped, run `data export /workspace/backups/owner-export.json`; it excludes evidence text and is not a restore source.

## Restore to a fresh target

Do not restore over your working database or clear production volumes to make the target empty. Preserve the original installation and backup. Prepare a separate empty PostgreSQL database and empty workspace, configure their `DATABASE_URL` and `KESTRI_WORKSPACE_DIR` for a local operator process, and keep the same `KESTRI_TELEGRAM_OWNER_ID`. Stop the original bot before switching installations. Development operator commands are host processes; their filesystem permissions are yours.

```sh
uv run kestri data restore .kestri/backups/UUID.json
uv run kestri data restore .kestri/backups/UUID.json --apply
uv run kestri data status
```

The first command validates without importing. Review its restore policy, then apply. The source backup must remain readable and mode `0600`. Imported evidence goes into the empty target workspace. Keep `.env` and credentials independently; the backup does not contain them. Do not run two Telegram pollers for one bot.

Start the intended recovered installation with its target configuration. Wait for the recovery notice: pending Telegram commands are discarded once. Inspect `/memory`, `/tasks`, `/runs`, and `/usage`. Re-enter any intended quarantined facts through `/remember`; explicitly resume only intended task IDs after reviewing their agreements. No historical delivery is automatically replayed. Ordinary restart remains a separate recovery path that retains existing authorizations.

## Handle failure

A validation error leaves the target unchanged. Controlled apply failures roll back records and remove new evidence. A sudden process/power failure can leave orphan files: preserve the source, inspect the failed target, and retry into a separate fresh database/workspace. Do not delete the only remaining data copy. Restore accepts schema 4 and 5 bundles, not arbitrary PostgreSQL dumps or exports. See the [data reference](../reference/data-lifecycle.md) for bounds and retention.
