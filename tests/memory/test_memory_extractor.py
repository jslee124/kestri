import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from kestri.agent.budget import Budget
from kestri.errors import PolicyDenied
from kestri.memory.extractor import (
    ExistingMemory,
    ExtractionBatch,
    MemoryExtractor,
    MemoryProposal,
    MemorySource,
    validate_proposal,
)
from kestri.redaction import Redactor
from tests.helpers import model_tool_call, offline_model, research_settings

NOW = datetime(2026, 10, 2, tzinfo=UTC)
TEXT = "我希望 Kestri 能帮助我找工作。"
QUOTE = "帮助我找工作"
REDACTOR = Redactor(["test-embedding-secret"])


def batch(**overrides: Any) -> ExtractionBatch:
    values = {
        "chat_id": 111,
        "memory_revision": 0,
        "memory_epoch": 0,
        "settings_generation": 1,
        "enabled": True,
        "activation_watermark": 0,
        "automatic_history_floor": 0,
        "sources": (
            MemorySource(
                message_id=10,
                chat_id=111,
                role="owner",
                provenance="direct",
                text=TEXT,
                created_at=NOW,
                fresh=True,
            ),
        ),
        **overrides,
    }
    return ExtractionBatch(**values)


def operation(**overrides: Any) -> dict[str, Any]:
    return {
        "action": "create",
        "category": "goal",
        "content": "希望 Kestri 帮助求职",
        "fact_key": "project.kestri.goal",
        "basis": "direct_statement",
        "source_refs": [
            {
                "message_id": 10,
                "quote": QUOTE,
                "start": TEXT.index(QUOTE),
                "end": TEXT.index(QUOTE) + len(QUOTE),
            }
        ],
        **overrides,
    }


def validate(op: dict[str, Any], source_batch: ExtractionBatch | None = None) -> Any:
    return validate_proposal(source_batch or batch(), MemoryProposal(operations=[op]), REDACTOR)


def test_direct_statement_and_empty_proposal() -> None:
    result = validate(operation())
    assert result.operations[0].action == "create"
    assert result.batch.settings_generation == 1
    assert validate_proposal(batch(), MemoryProposal(operations=[]), REDACTOR).operations == ()


def test_inference_remains_candidate() -> None:
    result = validate(operation(action="candidate", basis="inference"))
    assert result.operations[0].action == "candidate"
    for action in ("create", "reinforce", "replace"):
        with pytest.raises(PolicyDenied, match="InferenceMustRemainCandidate"):
            validate(operation(action=action, basis="inference"))


@pytest.mark.parametrize(
    "ref",
    [
        {"message_id": 11, "quote": QUOTE, "start": 0, "end": 6},
        {"message_id": 10, "quote": "编造原文", "start": 0, "end": 4},
        {"message_id": 10, "quote": QUOTE, "start": 0, "end": 1000},
        {"message_id": 10, "quote": QUOTE, "start": 6, "end": 2},
    ],
)
def test_fabricated_or_wrong_source_rejected(ref: dict[str, Any]) -> None:
    with pytest.raises(PolicyDenied, match="InvalidMemorySource"):
        validate(operation(source_refs=[ref]))


@pytest.mark.parametrize("provenance", ["forwarded", "external_reply", "context"])
def test_fresh_non_direct_messages_rejected(provenance: str) -> None:
    data = batch().model_dump()
    data["sources"][0]["provenance"] = provenance
    with pytest.raises(ValidationError):
        ExtractionBatch(**data)


@pytest.mark.parametrize(
    "change",
    [
        {"enabled": False},
        {"automatic_history_floor": 10},
        {"activation_watermark": 10},
        {"chat_id": 222},
    ],
)
def test_opt_in_cutoff_and_owner_boundaries(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        batch(**change)


def test_context_can_help_but_cannot_substantiate() -> None:
    context = MemorySource(
        message_id=11,
        chat_id=111,
        role="assistant",
        provenance="context",
        text=QUOTE,
        created_at=NOW,
        fresh=False,
    )
    source_batch = batch(sources=(*batch().sources, context))
    with pytest.raises(PolicyDenied, match="InvalidMemorySource"):
        validate(
            operation(
                source_refs=[{"message_id": 11, "quote": QUOTE, "start": 0, "end": len(QUOTE)}]
            ),
            source_batch,
        )
    assert validate(operation(), source_batch).operations


def test_update_requires_existing_current_and_older_target() -> None:
    memory = ExistingMemory(
        id=uuid4(),
        chat_id=111,
        content="希望 Kestri 帮助求职",
        category="goal",
        scope="global",
        revision=2,
        last_source_message_id=9,
        origin="explicit_command",
    )
    source_batch = batch(existing=(memory,))
    replacement = operation(action="replace", target_memory_id=memory.id, expected_revision=2)
    assert validate(replacement, source_batch).operations
    with pytest.raises(PolicyDenied, match="MemoryTargetStaleOrUnavailable"):
        validate({**replacement, "expected_revision": 1}, source_batch)
    with pytest.raises(PolicyDenied, match="MemoryTargetStaleOrUnavailable"):
        validate({**replacement, "target_memory_id": uuid4()}, source_batch)
    with pytest.raises(PolicyDenied, match="MemoryTargetStaleOrUnavailable"):
        validate(
            replacement, batch(existing=(memory.model_copy(update={"last_source_message_id": 11}),))
        )
    with pytest.raises(PolicyDenied, match="ReinforcementCannotChangeContent"):
        validate({**replacement, "action": "reinforce", "content": "变更了求职目标"}, source_batch)
    assert validate({**replacement, "action": "reinforce"}, source_batch).operations


def test_no_guessed_task_scope_or_target() -> None:
    with pytest.raises(PolicyDenied, match="MemoryScopeMismatch"):
        validate(operation(scope="task", task_id=uuid4()))
    with pytest.raises(PolicyDenied, match="UnexpectedMemoryTarget"):
        validate(operation(target_memory_id=uuid4()))


@pytest.mark.parametrize(
    "content", [" ", "test-embedding-secret", "API_KEY=abc", "sk-private", "[REDACTED]"]
)
def test_secret_and_blank_proposals_rejected(content: str) -> None:
    with pytest.raises(PolicyDenied, match="MemorySecretOrEmptyContent"):
        validate(operation(content=content))


def test_temporal_review_and_expiry() -> None:
    result = validate(operation(category="current_state"))
    assert result.operations[0].review_after == NOW + timedelta(days=30)
    with pytest.raises(PolicyDenied, match="MemoryExpiryNotFuture"):
        validate(operation(expires_at=NOW))
    with pytest.raises(PolicyDenied, match="MemoryReviewNotFuture"):
        validate(operation(review_after=NOW))
    with pytest.raises(ValidationError):
        MemoryProposal(operations=[operation(expires_at="2026-11-01T00:00:00")])


def test_strict_schema_and_duplicate_operations() -> None:
    with pytest.raises(ValidationError):
        MemoryProposal(operations=[operation(delete=True)])
    with pytest.raises(ValidationError):
        MemoryProposal(operations=[operation()] * 9)
    with pytest.raises(PolicyDenied, match="DuplicateMemoryOperation"):
        validate_proposal(batch(), MemoryProposal(operations=[operation()] * 2), REDACTOR)


class FakeControl:
    def __init__(self) -> None:
        self.checks = 0
        self.settlements: list[tuple[Any, ...]] = []
        self.store = self
        self.run_id = "test-run"

    async def ensure_active(self) -> None:
        self.checks += 1

    async def settle(self, *args: Any) -> None:
        self.settlements.append(args)


class FakeBudget:
    def __init__(self) -> None:
        self.settings = research_settings()
        self.control = FakeControl()
        self.reservations: list[tuple[str, int]] = []

    def model_cost(self, inputs: int, outputs: int) -> int:
        return inputs + outputs

    async def reserve(self, kind: str, amount: int) -> str:
        self.reservations.append((kind, amount))
        return "reservation"


async def test_real_agent_path_is_bounded_structured_and_charged() -> None:
    requests: list[dict[str, Any]] = []
    proposal = MemoryProposal(operations=[operation()])
    model, async_http, sync_http = offline_model(
        [model_tool_call("MemoryProposal", proposal.model_dump(mode="json"), "proposal-1")],
        requests,
    )
    budget = FakeBudget()
    try:
        result = await MemoryExtractor(model, REDACTOR).extract(batch(), cast(Budget, budget))
    finally:
        await async_http.aclose()
        sync_http.close()
    assert len(requests) == 1
    assert len(budget.reservations) == len(budget.control.settlements) == 1
    assert budget.control.checks >= 3
    assert result.operations[0].content == "希望 Kestri 帮助求职"
    assert {tool["function"]["name"] for tool in requests[0]["tools"]} == {"MemoryProposal"}
    assert "source_refs" in json.dumps(requests[0])


async def test_secret_source_rejected_before_model_or_budget() -> None:
    source = batch().sources[0].model_copy(update={"text": "test-embedding-secret"})
    extractor = MemoryExtractor(cast(Any, SimpleNamespace()), REDACTOR)
    budget = FakeBudget()
    with pytest.raises(PolicyDenied, match="MemorySourceContainsSecret"):
        await extractor.extract(batch(sources=(source,)), cast(Budget, budget))
    assert not budget.reservations
