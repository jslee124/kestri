"""Operator-only data lifecycle. Restore is deliberately quarantined and never replays work."""

import asyncio
import hashlib
import json
import os
import stat
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.types.json import Jsonb

from kestri.errors import PolicyDenied
from kestri.settings import DataSettings
from kestri.store import Store
from kestri.workspace import Workspace

TABLES = (
    "meta",
    "conversations",
    "runs",
    "tasks",
    "inbox",
    "messages",
    "outbox",
    "evidence",
    "usage",
    "events",
    "task_changes",
    "memories",
    "memory_changes",
)
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 50_000
FORMAT = "kestri-data-v1"


async def disk_operation[T](operation: Callable[..., T], *args: Any) -> T:
    """Keep a filesystem worker inside its database lease even during cancellation."""
    worker = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await worker
        raise


def encoded(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")


def write_private(path: Path, data: bytes) -> None:
    if len(data) > MAX_BYTES:
        raise PolicyDenied("BackupSizeLimit")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise PolicyDenied("BackupDirectorySymlink")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def read_private(path: Path) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > MAX_BYTES:
            raise PolicyDenied("BackupFilePolicy")
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise PolicyDenied("BackupSizeLimit")
    bundle = json.loads(data)
    if not isinstance(bundle, dict) or set(bundle) != {"sha256", "payload"}:
        raise PolicyDenied("InvalidBackup")
    payload = bundle["payload"]
    if hashlib.sha256(encoded(payload)).hexdigest() != bundle["sha256"]:
        raise PolicyDenied("BackupChecksumMismatch")
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise PolicyDenied("BackupFormatMismatch")
    return payload


class DataService:
    def __init__(self, store: Store, workspace: Workspace, settings: DataSettings) -> None:
        self.store = store
        self.workspace = workspace
        self.settings = settings

    @asynccontextmanager
    async def exclusive(self, *, operator: bool = True, bot_id: int | None = None) -> Any:
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                locked = await (
                    await conn.execute(
                        "SELECT pg_try_advisory_xact_lock(hashtext('kestri-data')) AS locked"
                    )
                ).fetchone()
                if not locked or not locked["locked"]:
                    raise PolicyDenied("MaintenanceAlreadyRunning")
                identity = await (
                    await conn.execute("SELECT value FROM kestri.meta WHERE key='identity'")
                ).fetchone()
                if identity:
                    if identity["value"]["owner_id"] != self.settings.telegram_owner_id:
                        raise PolicyDenied("DatabaseIdentityMismatch")
                    bot_id = identity["value"]["bot_id"]
                if operator and bot_id is not None:
                    lease = await (
                        await conn.execute(
                            "SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS locked",
                            (f"kestri-bot-{bot_id}",),
                        )
                    ).fetchone()
                    if not lease or not lease["locked"]:
                        raise PolicyDenied("StopApplicationBeforeMaintenance")
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations ORDER BY chat_id FOR UPDATE"
                )
                yield conn

    async def status(self) -> dict[str, Any]:
        counts = {}
        for table in TABLES:
            row = await self.store.one(
                sql.SQL("SELECT count(*) AS n FROM kestri.{}").format(sql.Identifier(table))
            )
            counts[table] = row["n"] if row else 0
        last = await self.store.one("SELECT value FROM kestri.meta WHERE key='maintenance'")
        return {"counts": counts, "last_maintenance": last["value"] if last else None}

    async def backup(self, path: Path | None = None, *, export: bool = False) -> Path:
        tables: dict[str, list[dict[str, Any]]] = {}
        attachments: dict[str, str] = {}
        size = total = 0
        async with self.exclusive() as conn:
            for table in TABLES:
                tables[table] = []
                async with conn.cursor(name=f"backup_{table}") as cursor:
                    await cursor.execute(
                        sql.SQL("SELECT * FROM kestri.{}").format(sql.Identifier(table))
                    )
                    async for row in cursor:
                        size += len(encoded(row))
                        total += 1
                        if size > MAX_BYTES // 2 or total > MAX_ROWS:
                            raise PolicyDenied("BackupSizeLimit")
                        tables[table].append(row)
            if not export:
                for record in tables["evidence"]:
                    if record["status"] != "retrieved":
                        continue
                    content, truncated = await disk_operation(
                        self.workspace.read,
                        str(record["run_id"]),
                        str(record["id"]),
                        64_000,
                    )
                    if truncated:
                        raise PolicyDenied("EvidenceSizeLimit")
                    size += len(content.encode("utf-8"))
                    if size > MAX_BYTES // 2:
                        raise PolicyDenied("BackupSizeLimit")
                    attachments[f"{record['run_id']}/{record['id']}"] = content
            payload = {
                "format": FORMAT,
                "kind": "export" if export else "backup",
                "schema": 4,
                "created_at": datetime.now(UTC).isoformat(),
                "tables": tables,
                "evidence_text": attachments,
                "checkpoints": "excluded-reset-on-restore",
            }
            raw = encoded(payload)
            bundle = encoded({"sha256": hashlib.sha256(raw).hexdigest(), "payload": payload})
            path = path or self.workspace.root / "backups" / f"{uuid4()}.json"
            await disk_operation(write_private, path, bundle)
        return path

    async def restore(self, path: Path, *, apply: bool = False) -> dict[str, Any]:
        payload = await disk_operation(read_private, path)
        if payload.get("kind") != "backup" or payload.get("schema") != 4:
            raise PolicyDenied("NotRestorableBackup")
        tables = payload.get("tables")
        attachments = payload.get("evidence_text")
        if (
            not isinstance(tables, dict)
            or set(tables) != set(TABLES)
            or not isinstance(attachments, dict)
        ):
            raise PolicyDenied("InvalidBackupTables")
        total = 0
        for rows in tables.values():
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise PolicyDenied("InvalidBackupRows")
            total += len(rows)
            for row in rows:
                if "chat_id" in row and row["chat_id"] != self.settings.telegram_owner_id:
                    raise PolicyDenied("BackupOwnerMismatch")
        if total > MAX_ROWS:
            raise PolicyDenied("BackupSizeLimit")
        identities = [row["value"] for row in tables["meta"] if row.get("key") == "identity"]
        if len(identities) != 1 or identities[0].get("owner_id") != self.settings.telegram_owner_id:
            raise PolicyDenied("BackupOwnerMismatch")
        bot_id = identities[0].get("bot_id")
        if type(bot_id) is not int or bot_id <= 0:
            raise PolicyDenied("InvalidBackupIdentity")
        expected = {
            f"{r['run_id']}/{r['id']}" for r in tables["evidence"] if r["status"] == "retrieved"
        }
        if set(attachments) != expected:
            raise PolicyDenied("BackupEvidenceMismatch")
        for name, content in attachments.items():
            parts = name.split("/")
            if len(parts) != 2 or any(str(UUID(part)) != part for part in parts):
                raise PolicyDenied("InvalidBackupEvidenceID")
            if not isinstance(content, str) or len(content) > 64_000:
                raise PolicyDenied("EvidenceSizeLimit")
        report = {
            "rows": total,
            "evidence_files": len(attachments),
            "applied": apply,
            "restore_policy": (
                "memories quarantined; tasks paused; no execution or delivery replay; "
                "pending Telegram updates discarded at first startup"
            ),
        }
        created: list[tuple[str, str]] = []
        try:
            async with self.exclusive(bot_id=bot_id) as conn:
                for table in TABLES:
                    row = await (
                        await conn.execute(
                            sql.SQL("SELECT count(*) AS n FROM kestri.{}").format(
                                sql.Identifier(table)
                            )
                        )
                    ).fetchone()
                    if row and row["n"]:
                        raise PolicyDenied("RestoreRequiresEmptyDatabase")
                if any(entry.name != "backups" for entry in self.workspace.root.iterdir()):
                    raise PolicyDenied("RestoreRequiresEmptyWorkspace")
                checkpoint = await (
                    await conn.execute("SELECT to_regclass('public.checkpoints') AS name")
                ).fetchone()
                if checkpoint and checkpoint["name"]:
                    row = await (
                        await conn.execute("SELECT count(*) AS n FROM public.checkpoints")
                    ).fetchone()
                    if row and row["n"]:
                        raise PolicyDenied("RestoreRequiresEmptyCheckpoints")
                await conn.execute("SET CONSTRAINTS ALL DEFERRED")
                for table in TABLES:
                    columns = await (
                        await conn.execute(
                            (
                                "SELECT column_name,data_type FROM information_schema.columns "
                                "WHERE "
                                "table_schema='kestri' AND table_name=%s ORDER BY ordinal_position"
                            ),
                            (table,),
                        )
                    ).fetchall()
                    names = [c["column_name"] for c in columns]
                    for original in tables[table]:
                        if set(original) != set(names):
                            raise PolicyDenied("BackupColumnMismatch")
                        row = dict(original)
                        if table == "conversations":
                            row["thread_id"] = None
                            row["memory_epoch"] += 1
                        elif table == "memories" and row["status"] == "active":
                            row["status"] = "quarantined"
                        elif table == "tasks" and row["status"] != "deleted":
                            row["status"], row["restored"] = "paused", True
                        elif table == "runs" and row["status"] in {"queued", "running"}:
                            (
                                row["status"],
                                row["cancel_requested"],
                                row["error_type"],
                            ) = (
                                "interrupted",
                                True,
                                "RestoreQuarantine",
                            )
                        elif table == "outbox" and row["status"] in {
                            "pending",
                            "sending",
                        }:
                            row["status"], row["error_type"] = (
                                "uncertain",
                                "RestoreQuarantine",
                            )
                        elif table == "usage" and row["state"] == "reserved":
                            row["state"] = "unknown"
                        if apply:
                            values = [
                                Jsonb(row[c["column_name"]])
                                if c["data_type"] == "jsonb"
                                else row[c["column_name"]]
                                for c in columns
                            ]
                            await conn.execute(
                                sql.SQL("INSERT INTO kestri.{} ({}) VALUES ({})").format(
                                    sql.Identifier(table),
                                    sql.SQL(",").join(map(sql.Identifier, names)),
                                    sql.SQL(",").join(sql.Placeholder() for _ in names),
                                ),
                                values,
                            )
                if apply:
                    await conn.execute(
                        "INSERT INTO kestri.meta(key,value) VALUES ('restore_quarantine',%s) "
                        "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                        (Jsonb({"pending_updates": True}),),
                    )
                    for name, content in attachments.items():
                        run_id, evidence_id = name.split("/")
                        created.append((run_id, evidence_id))
                        await disk_operation(
                            self.workspace.write,
                            run_id,
                            evidence_id,
                            content,
                        )
                    for table, column in (
                        ("messages", "id"),
                        ("outbox", "sequence"),
                        ("events", "sequence"),
                    ):
                        await conn.execute(
                            sql.SQL(
                                "SELECT setval(pg_get_serial_sequence(%s,%s),"
                                "GREATEST(COALESCE((SELECT "
                                "max({}) FROM kestri.{}),0),1),EXISTS(SELECT 1 FROM kestri.{}))"
                            ).format(
                                sql.Identifier(column),
                                sql.Identifier(table),
                                sql.Identifier(table),
                            ),
                            (f"kestri.{table}", column),
                        )
        except BaseException:
            for run_id, evidence_id in created:
                await disk_operation(self.workspace.remove, run_id, evidence_id)
                directory = self.workspace.root / run_id
                try:
                    directory.rmdir()
                except OSError:
                    pass
            raise
        return report

    async def cleanup(
        self,
        *,
        apply: bool = False,
        before: datetime | None = None,
        erase: bool = False,
        operator: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        archive_cutoff = before or now - timedelta(days=self.settings.archive_retention_days)
        evidence_cutoff = (
            now if erase else now - timedelta(days=self.settings.evidence_retention_days)
        )
        log_cutoff = now if erase else now - timedelta(days=self.settings.log_retention_days)
        if erase:
            archive_cutoff = evidence_cutoff = log_cutoff = datetime.max.replace(tzinfo=UTC)
        if archive_cutoff.tzinfo is None:
            raise PolicyDenied("TimezoneRequired")
        report: dict[str, Any] = {
            "applied": apply,
            "archive_before": archive_cutoff.isoformat(),
            "deferred": False,
        }
        async with self.exclusive(operator=operator) as conn:
            busy = await (
                await conn.execute(
                    "SELECT EXISTS(SELECT 1 FROM kestri.runs WHERE status IN "
                    "('queued','running')) OR EXISTS(SELECT 1 FROM kestri.outbox WHERE "
                    "status IN ('pending','sending')) AS busy"
                )
            ).fetchone()
            if busy and busy["busy"]:
                report["deferred"] = True
                return report
            for key, query, cutoff in (
                (
                    "messages",
                    "SELECT count(*) AS n FROM kestri.messages WHERE created_at<%s",
                    archive_cutoff,
                ),
                (
                    "run_content",
                    (
                        "SELECT count(*) AS n FROM kestri.runs WHERE created_at<%s AND NOT "
                        "history_expired"
                    ),
                    archive_cutoff,
                ),
                (
                    "events",
                    "SELECT count(*) AS n FROM kestri.events WHERE created_at<%s",
                    log_cutoff,
                ),
            ):
                row = await (await conn.execute(query, (cutoff,))).fetchone()
                report[key] = row["n"] if row else 0
            evidence = await (
                await conn.execute(
                    "SELECT count(*) AS n FROM kestri.evidence WHERE status='retrieved' AND "
                    "(created_at<%s OR run_id IN (SELECT id FROM kestri.runs WHERE created_at<%s))",
                    (evidence_cutoff, archive_cutoff),
                )
            ).fetchone()
            report["evidence"] = evidence["n"] if evidence else 0
            if not apply:
                return report
            if erase:
                await conn.execute(
                    "UPDATE kestri.memories SET status='forgotten',content='',updated_at=%s",
                    (now,),
                )
                await conn.execute(
                    (
                        "UPDATE kestri.tasks SET "
                        "status='deleted',title='',instructions='',timezone='UTC',local_time='00:"
                        "00',weekdays=ARRAY[0],catch_up_seconds=0,next_due=%s,revision=revision+1"
                        ",updated_at=%s"
                    ),
                    (now, now),
                )
            await conn.execute("DELETE FROM kestri.messages WHERE created_at<%s", (archive_cutoff,))
            await conn.execute(
                (
                    "UPDATE kestri.runs SET request='',result=NULL,history_expired=true "
                    "WHERE created_at<%s"
                ),
                (archive_cutoff,),
            )
            await conn.execute(
                "UPDATE kestri.outbox SET content='' WHERE created_at<%s",
                (archive_cutoff,),
            )
            for table in ("task_changes", "memory_changes"):
                await conn.execute(
                    sql.SQL("UPDATE kestri.{} SET result='' WHERE created_at<%s").format(
                        sql.Identifier(table)
                    ),
                    (archive_cutoff,),
                )
            await conn.execute(
                (
                    "UPDATE kestri.memories SET content='' WHERE status!='active' AND "
                    "status!='quarantined' AND updated_at<%s"
                ),
                (archive_cutoff,),
            )
            await conn.execute(
                "UPDATE kestri.tasks SET title='',instructions='' "
                "WHERE status='deleted' AND updated_at<%s",
                (archive_cutoff,),
            )
            if report["messages"] or report["run_content"] or report["evidence"] or erase:
                await conn.execute(
                    (
                        "UPDATE kestri.conversations SET "
                        "thread_id=NULL,memory_epoch=memory_epoch+1,updated_at=%s"
                    ),
                    (now,),
                )
                for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                    exists = await (
                        await conn.execute("SELECT to_regclass(%s) AS name", (f"public.{table}",))
                    ).fetchone()
                    if exists and exists["name"]:
                        await conn.execute(
                            sql.SQL("DELETE FROM public.{}").format(sql.Identifier(table))
                        )
            await conn.execute("DELETE FROM kestri.events WHERE created_at<%s", (log_cutoff,))
            await conn.execute(
                (
                    "UPDATE kestri.evidence SET "
                    "status='expired',metadata=jsonb_build_object('cleanup_pending',true) "
                    "WHERE status='retrieved' AND (created_at<%s OR run_id IN (SELECT id "
                    "FROM kestri.runs WHERE created_at<%s))"
                ),
                (evidence_cutoff, archive_cutoff),
            )
            await conn.execute(
                "UPDATE kestri.evidence SET url='',title='' WHERE run_id IN (SELECT id "
                "FROM kestri.runs WHERE history_expired)"
            )
            await conn.execute(
                (
                    "INSERT INTO kestri.meta(key,value) VALUES ('maintenance',%s) ON "
                    "CONFLICT(key) DO UPDATE SET value=EXCLUDED.value"
                ),
                (Jsonb({**report, "at": now.isoformat()}),),
            )
        pending = await self.store.all(
            "SELECT id,run_id FROM kestri.evidence WHERE metadata->>'cleanup_pending'='true'"
        )
        for record in pending:
            await disk_operation(self.workspace.remove, str(record["run_id"]), str(record["id"]))
            await self.store.execute(
                "UPDATE kestri.evidence SET metadata='{}' WHERE id=%s", (record["id"],)
            )
        report["backup_files"] = await disk_operation(self.prune_backups, now, erase)
        await self.store.execute(
            "UPDATE kestri.meta SET value=%s WHERE key='maintenance'",
            (Jsonb({**report, "at": now.isoformat()}),),
        )
        return report

    def prune_backups(self, now: datetime, erase: bool = False) -> int:
        folder = self.workspace.root / "backups"
        if not folder.exists():
            return 0
        if folder.is_symlink():
            raise PolicyDenied("BackupDirectorySymlink")
        removed = 0
        for path in folder.iterdir():
            try:
                UUID(path.stem)
            except ValueError:
                continue
            if path.suffix != ".json" or path.is_symlink() or not path.is_file():
                continue
            cutoff = (now - timedelta(days=self.settings.backup_retention_days)).timestamp()
            if erase or path.stat().st_mtime < cutoff:
                payload = read_private(path)
                if payload.get("kind") == "backup":
                    path.unlink()
                    removed += 1
        return removed

    async def maintaining(self) -> None:
        while True:
            try:
                await self.cleanup(apply=True, operator=False)
            except Exception as error:
                # Never dump private database/file/provider exception details.
                await self.store.execute(
                    (
                        "INSERT INTO kestri.meta(key,value) VALUES ('maintenance',%s) ON "
                        "CONFLICT(key) DO UPDATE SET value=EXCLUDED.value"
                    ),
                    (
                        Jsonb(
                            {
                                "error_type": type(error).__name__,
                                "at": datetime.now(UTC).isoformat(),
                            }
                        ),
                    ),
                )
            await asyncio.sleep(self.settings.maintenance_interval_seconds)
