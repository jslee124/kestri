"""Deterministic two-turn live smoke and minimal, secret-free evidence."""

import json
import os
import platform
import re
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage

from kestri.agent.runtime import AgentSession, TurnResult
from kestri.settings import Settings

SMOKE_PROMPTS = (
    "Use checked_add to add 17 and 25. State the result.",
    "Use checked_add to add 8 to the previous result. State the new result.",
)


def verify_turn(result: TurnResult, expected: int, previous_count: int) -> bool:
    new_messages = result.messages[previous_count:]
    return (
        result.status == "completed"
        and any(isinstance(message, AIMessage) and message.tool_calls for message in new_messages)
        and any(
            isinstance(message, ToolMessage)
            and message.status == "success"
            and message.content == str(expected)
            for message in new_messages
        )
        and re.search(rf"(?<!\d){expected}(?!\d)", result.answer) is not None
    )


def turn_evidence(result: TurnResult, previous_count: int, secret: str) -> dict[str, Any]:
    """Keep observable tool/usage evidence, excluding provider reasoning and raw errors."""
    new_messages = result.messages[previous_count:]
    model_messages = [message for message in new_messages if isinstance(message, AIMessage)]
    tool_results = [message for message in new_messages if isinstance(message, ToolMessage)]
    return {
        "status": result.status,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "error_type": result.error_type,
        "answer": result.answer.replace(secret, "[REDACTED]"),
        "model_responses": len(model_messages),
        "tool_calls": [
            {"name": call["name"], "arguments": call["args"]}
            for message in model_messages
            for call in message.tool_calls
        ],
        "tool_results": [
            {
                "name": message.name,
                "status": message.status,
                "content": message.content,
            }
            for message in tool_results
        ],
        "usage": [message.usage_metadata for message in model_messages],
        "reasoning_present": [
            bool(message.additional_kwargs.get("reasoning_content")) for message in model_messages
        ],
    }


async def run_smoke(settings: Settings) -> dict[str, Any]:
    session = AgentSession(settings)
    turns: list[dict[str, Any]] = []
    previous_count = 0
    try:
        for prompt, expected in zip(SMOKE_PROMPTS, (42, 50), strict=True):
            result = await session.ask(prompt)
            evidence = turn_evidence(
                result, previous_count, settings.deepseek_api_key.get_secret_value()
            )
            evidence["verified"] = verify_turn(result, expected, previous_count)
            turns.append(evidence)
            previous_count = len(result.messages)
            if not evidence["verified"]:
                break
    finally:
        await session.aclose()
    return {
        "schema_version": 1,
        "kind": "deepseek-live-smoke",
        "recorded_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "packages": {
            package: version(package)
            for package in ("langchain", "langchain-deepseek", "langgraph")
        },
        "provider": "deepseek-official",
        "model": settings.model,
        "thinking_mode": settings.thinking_mode,
        "limits": {
            "model_calls_per_turn": settings.max_model_calls,
            "tool_calls_per_turn": settings.max_tool_calls,
            "seconds_per_turn": settings.run_timeout_seconds,
            "output_tokens_per_request": settings.max_output_tokens,
            "sdk_retries": 0,
        },
        "passed": len(turns) == 2 and all(turn["verified"] for turn in turns),
        "turns": turns,
    }


def save_evidence(settings: Settings, evidence: dict[str, Any]) -> Path:
    directory = settings.evidence_dir
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f"smoke-{uuid4().hex}.json"
    raw = json.dumps(evidence, indent=2, ensure_ascii=False)
    # Final defense for all fields, including unexpected provider-generated tool arguments.
    raw = raw.replace(settings.deepseek_api_key.get_secret_value(), "[REDACTED]")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(raw + "\n")
    return path
