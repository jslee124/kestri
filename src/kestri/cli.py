"""Developer entry point for the M0 live integration check."""

import argparse
import asyncio
import sys

from pydantic import ValidationError

from kestri.application import run_telegram, show_telegram_ids
from kestri.settings import ResearchSettings, Settings, TelegramCredentials
from kestri.smoke import run_smoke, save_evidence


def main() -> int:
    parser = argparse.ArgumentParser(prog="kestri")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("smoke", help="Run the bounded two-turn DeepSeek integration check")
    subcommands.add_parser("telegram", help="Run the owner-only research and recurring-task bot")
    subcommands.add_parser("telegram-id", help="Inspect pending private user IDs without enrolling")
    arguments = parser.parse_args()
    if arguments.command != "smoke":
        try:
            if arguments.command == "telegram-id":
                asyncio.run(show_telegram_ids(TelegramCredentials()))
            else:
                asyncio.run(run_telegram(ResearchSettings()))
        except ValidationError:
            print(
                "Configuration invalid. Check the Telegram configuration reference.",
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
        print("Configuration invalid. Check .env and the configuration reference.", file=sys.stderr)
        return 2
    try:
        evidence = asyncio.run(run_smoke(settings))
        path = save_evidence(settings, evidence)
    except KeyboardInterrupt:
        print("Cancelled. No further model calls will be initiated.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Smoke check failed ({type(error).__name__}); details suppressed.", file=sys.stderr)
        return 1
    print(f"Evidence: {path}")
    if evidence["passed"]:
        print("PASS: real tool interaction and multi-turn follow-up verified.")
        return 0
    for index, turn in enumerate(evidence["turns"], 1):
        if not turn["verified"]:
            print(f"FAIL: turn {index}, status={turn['status']}, type={turn['error_type']}.")
    return 1
