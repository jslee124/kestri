"""Application entry points and local operator controls."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from kestri.application import run_telegram, show_telegram_ids
from kestri.data import DataService
from kestri.embedding import run_embedding_smoke, save_embedding_evidence
from kestri.redaction import Redactor
from kestri.settings import (
    DataSettings,
    EmbeddingSettings,
    ResearchSettings,
    Settings,
    TelegramCredentials,
)
from kestri.smoke import run_smoke, save_evidence
from kestri.store import Store
from kestri.workspace import Workspace


async def run_data(settings: DataSettings, arguments: argparse.Namespace) -> None:
    secrets = [settings.database_url.get_secret_value()]
    if settings.dashscope_api_key is not None:
        secrets.append(settings.dashscope_api_key.get_secret_value())
    store = Store(
        settings.database_url.get_secret_value(),
        Redactor(secrets),
    )
    try:
        if arguments.action == "status":
            await store.pool.open(wait=True)
        else:
            await store.open()
        service = DataService(store, Workspace(settings.workspace_dir), settings)
        if arguments.action == "status":
            result = await service.status()
        elif arguments.action in {"backup", "export"}:
            path = await service.backup(arguments.path, export=arguments.action == "export")
            result = {"path": str(path.absolute()), "private": True}
        elif arguments.action == "restore":
            result = await service.restore(arguments.path, apply=arguments.apply)
        else:
            before = None
            if arguments.action == "delete-history":
                before = (
                    datetime.fromisoformat(arguments.before)
                    if arguments.before
                    else datetime.now(UTC)
                )
            result = await service.cleanup(
                apply=arguments.apply, before=before, erase=arguments.action == "erase"
            )
        print(json.dumps(result, ensure_ascii=False, default=str))
    finally:
        await store.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="kestri")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("smoke", help="Run the bounded two-turn DeepSeek integration check")
    subcommands.add_parser(
        "embedding-smoke", help="Check Beijing embeddings using three fixed non-private texts"
    )
    subcommands.add_parser("telegram", help="Run the owner-only research and recurring-task bot")
    subcommands.add_parser("telegram-id", help="Inspect pending private user IDs without enrolling")
    data = subcommands.add_parser("data", help="Local-only archive, backup, restore, and retention")
    actions = data.add_subparsers(dest="action", required=True)
    actions.add_parser("status", help="Database counts and last maintenance outcome")
    for action in ("backup", "export"):
        command = actions.add_parser(action, help="Write a private logical bundle; stop app first")
        command.add_argument("path", type=Path, nargs="?" if action == "backup" else None)
    command = actions.add_parser(
        "restore",
        help=(
            "Restore into an empty database/workspace; quarantine state and "
            "discard pending Telegram updates"
        ),
    )
    command.add_argument("path", type=Path)
    command.add_argument("--apply", action="store_true", help="Apply; default only validates")
    for action in ("cleanup", "delete-history", "erase"):
        command = actions.add_parser(
            action, help="Preview lifecycle changes; stop app before applying"
        )
        command.add_argument("--apply", action="store_true", help="Apply; default is a dry run")
        if action == "delete-history":
            command.add_argument("--before", help="Timezone-aware ISO cutoff; default all history")
    arguments = parser.parse_args()
    if arguments.command != "smoke":
        try:
            if arguments.command == "embedding-smoke":
                embedding_settings = EmbeddingSettings()
                result = asyncio.run(run_embedding_smoke(embedding_settings))
                path = save_embedding_evidence(embedding_settings, result)
                print(f"Evidence: {path}")
                print(json.dumps(result, ensure_ascii=False))
                return 0 if result["passed"] else 1
            elif arguments.command == "data":
                asyncio.run(run_data(DataSettings(), arguments))
            elif arguments.command == "telegram-id":
                asyncio.run(show_telegram_ids(TelegramCredentials()))
            else:
                asyncio.run(run_telegram(ResearchSettings()))
        except ValidationError:
            print(
                "Configuration invalid. Check the command's configuration reference.",
                file=sys.stderr,
            )
            return 2
        except KeyboardInterrupt, asyncio.CancelledError:
            print("Stopped. Accepted messages and saved results remain in PostgreSQL.")
            return 130
        except Exception as error:
            print(
                f"Startup or execution failed ({type(error).__name__}); details suppressed.",
                file=sys.stderr,
            )
            return 1
        return 0
    try:
        settings = Settings()
    except ValidationError:
        print(
            "Configuration invalid. Check .env and the configuration reference.",
            file=sys.stderr,
        )
        return 2
    try:
        evidence = asyncio.run(run_smoke(settings))
        path = save_evidence(settings, evidence)
    except KeyboardInterrupt:
        print("Cancelled. No further model calls will be initiated.", file=sys.stderr)
        return 130
    except Exception as error:
        print(
            f"Smoke check failed ({type(error).__name__}); details suppressed.",
            file=sys.stderr,
        )
        return 1
    print(f"Evidence: {path}")
    if evidence["passed"]:
        print("PASS: real tool interaction and multi-turn follow-up verified.")
        return 0
    for index, turn in enumerate(evidence["turns"], 1):
        if not turn["verified"]:
            print(f"FAIL: turn {index}, status={turn['status']}, type={turn['error_type']}.")
    return 1
