import pytest
from pydantic import ValidationError

from kestri.tools import checked_add


async def test_addition_has_no_arbitrary_execution() -> None:
    assert await checked_add.ainvoke({"left": 17, "right": 25}) == "42"
    with pytest.raises(ValidationError):
        await checked_add.ainvoke({"left": "__import__('os').system('id')", "right": 0})


async def test_out_of_scope_inputs_and_total_are_rejected() -> None:
    with pytest.raises(ValidationError):
        await checked_add.ainvoke(
            {
                "left": 1,
                "right": 2,
                "path": "/etc/passwd",
            }
        )
    with pytest.raises(ValidationError):
        await checked_add.ainvoke({"left": True, "right": 2})
    with pytest.raises(ValidationError):
        await checked_add.ainvoke({"left": 1_000_001, "right": 0})
    with pytest.raises(ValueError, match="permitted range"):
        await checked_add.ainvoke({"left": 1_000_000, "right": 1})
