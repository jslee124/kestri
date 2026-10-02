"""Shared isolated automatic-memory scenario fixtures."""

from typing import Any

from kestri.memory.extractor import MemoryProposal
from kestri.memory.service import MemoryService
from tests.helpers import accept_memory_control_run, research_settings

TEXT = "我希望 Kestri 帮助我找工作。"


async def enable(store: Any, identity: int = 1, enabled: bool = True) -> None:
    await store.accept(
        identity, 111, identity, "/memory auto " + ("on" if enabled else "off"), None, "memory", 8
    )


async def enqueue(
    store: Any, identity: int = 2, text: str = TEXT, provenance: str = "direct"
) -> None:
    await store.accept(identity, 111, identity, text, None, None, 8, provenance=provenance)
    run = await store.claim_run()
    assert run is not None
    await store.finish(run["id"], "completed", "研究回答")


def proposal(batch: Any, **changes: Any) -> MemoryProposal:
    source = next(s for s in batch.sources if s.fresh)
    op = {
        "action": "create",
        "category": "goal",
        "content": "希望 Kestri 帮助求职",
        "fact_key": "project.kestri.goal",
        "basis": "direct_statement",
        "source_refs": [
            {
                "message_id": source.message_id,
                "quote": source.text,
                "start": 0,
                "end": len(source.text),
            }
        ],
        **changes,
    }
    return MemoryProposal(operations=[op])


async def apply_control(store: Any, text: str, identity: int) -> str:
    run = await accept_memory_control_run(store, text, identity)
    result = await MemoryService(store, research_settings()).apply(run)
    await store.finish(run["id"], "completed", result)
    return result
