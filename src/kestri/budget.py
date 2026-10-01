"""Durable conservative reservations before each billable operation."""

import asyncio
import json
from decimal import ROUND_CEILING, Decimal
from typing import Any

from kestri.settings import ResearchSettings
from kestri.store import Store


def micro_usd(value: Decimal) -> int:
    return int((value * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


class RunControl:
    def __init__(self, store: Store, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.cancel = asyncio.Event()

    async def ensure_active(self) -> None:
        if self.cancel.is_set() or await self.store.cancelled(self.run_id):
            raise asyncio.CancelledError


class Budget:
    def __init__(self, settings: ResearchSettings, control: RunControl) -> None:
        self.settings = settings
        self.control = control

    def model_cost(self, input_tokens: int, output_tokens: int) -> int:
        # A million tokens times a USD-per-million rate gives micro-USD directly.
        return int(
            (
                input_tokens * self.settings.input_usd_per_million
                + output_tokens * self.settings.output_usd_per_million
            ).to_integral_value(rounding=ROUND_CEILING)
        )

    async def reserve(self, kind: str, amount: int) -> str:
        await self.control.ensure_active()
        return await self.control.store.reserve(
            self.control.run_id,
            kind,
            amount,
            micro_usd(self.settings.monthly_budget_usd),
            micro_usd(self.settings.run_budget_usd),
        )

    async def provider_usage(self, reservation: str, metadata: dict[str, Any]) -> None:
        await self.control.store.settle(reservation, metadata)


def conservative_input_size(messages: list[Any], tools: list[Any]) -> int:
    """UTF-8 byte estimate plus framing; intentionally overcounts ordinary text.

    This is a local admission heuristic, not the provider's exact tokenizer.
    Include reasoning, tool schemas, and message metadata; never silently trim.
    """
    payload = {
        "messages": [message.model_dump() for message in messages],
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.get_input_schema().model_json_schema(),
            }
            if hasattr(tool, "get_input_schema")
            else tool
            for tool in tools
        ],
    }
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")) + 2048
