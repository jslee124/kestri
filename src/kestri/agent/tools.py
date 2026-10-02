"""A deliberately narrow tool for the M0 integration check."""

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field


class AddInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    left: int = Field(strict=True, ge=-1_000_000, le=1_000_000)
    right: int = Field(strict=True, ge=-1_000_000, le=1_000_000)


@tool(args_schema=AddInput)
async def checked_add(left: int, right: int) -> str:
    """Add two integers; each operand and the total must be within +/- 1,000,000."""
    total = left + right
    if abs(total) > 1_000_000:
        raise ValueError("The total exceeds the permitted range.")
    return str(total)
