# Operate the local assistant

[简体中文](operate-local-agent.zh-CN.md) · [Documentation](../README.md)

Updated: 2026-10-02.

## Start and inspect

Complete the [Telegram setup tutorial](../tutorials/telegram-research.md), then use one deployment:

```sh
docker compose up --build -d
docker compose ps
docker compose logs --tail 50 app
docker compose exec app /app/.venv/bin/kestri data status
```

App and database use `restart: unless-stopped`. Docker must itself be running; this does not configure login startup or wake a sleeping laptop. The app healthcheck queries database counts once per minute; it is database liveness, not proof of Telegram/model/search availability. Docker restart policy restarts exited containers, not merely unhealthy ones. Inspect logs/status and restart deliberately if health stays unhealthy.

Base Compose publishes no database port. The app is non-root, has a read-only root, dedicated workspace volume, bounded temporary storage/resources, dropped capabilities, and no host-home or Docker-socket mount. Development overrides expose loopback PostgreSQL and do not isolate a host Python process. Containers are not a separate VM security guarantee. Web/model/messaging still contact external services.

For the deployed Memory v2 vector installation, keep `-f compose.yaml -f compose.vector.yaml` on build/up commands. Using only the base file can replace the extension-enabled PostgreSQL image. Follow [Memory v2 deployment](deploy-memory-v2.md) for upgrade, backup and rollback instructions.

## Everyday use and recovery

In Telegram, use the collapsible Menu for every registered command. Ask a public research question, reply to its answer, create an explicit daily/weekly task, and save facts through `/remember`. `/status` and `/runs` inspect execution and delivery; `/usage` reports local estimated spending. `/stop` cancels the foreground run, or accepts a run ID. `/new` resets idle conversation context while preserving memory, tasks, and archives. The [task](../reference/tasks.md) and [memory](../reference/memory-and-context.md) references explain controls.

Stop with `docker compose stop app`; restart with `docker compose start app`. Keep volumes. Accepted inbound requests survive, interrupted runs are reported without blind research replay, saved results survive, and uncertain sends are not blindly resent. Tasks can coalesce eligible missed occurrences within their agreement's catch-up window. Sleep/stopped Docker delays scheduling. Do not use `docker compose down -v` for routine operation.

For upgrades, stop the app, [back up](backup-and-restore.md), inspect the change/migration notes, build, and start. Schema migration 4 is additive but introduces new columns/statuses; arbitrary downgrade or older-code startup after migration is not supported. Keep the source revision and private snapshot needed for recovery.

## Retention and explicit deletion

Automatic retention runs while idle. Inspect `data status` for the latest maintenance counts or safe error type. For manual maintenance stop the app and preview:

```sh
docker compose stop app
docker compose run --rm --no-deps app data cleanup
docker compose run --rm --no-deps app data cleanup --apply
docker compose start app
```

To delete original history, substitute `data delete-history --before 2026-10-01T00:00:00+08:00`, review, and add `--apply`. This preserves active memory and tasks; use explicit memory/task controls separately. `data erase` previews local content erasure; `data erase --apply` also forgets memory and deletes agreements and managed backups. Read the [data reference](../reference/data-lifecycle.md) before applying. External copies and provider/Telegram data remain separate. An application/database error reports its class without raw private exception details; fix configuration/storage/network before restarting rather than increasing limits blindly.
