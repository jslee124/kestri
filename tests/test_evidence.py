import json
import stat
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from kestri.runtime import TurnResult
from kestri.smoke import save_evidence, turn_evidence, verify_turn

from .conftest import test_settings


def test_reasoning_and_credentials_are_not_written(tmp_path: Path) -> None:
    settings = test_settings(evidence_dir=tmp_path)
    secret = settings.deepseek_api_key.get_secret_value()
    result = TurnResult(
        "completed",
        f"42 {secret}",
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "checked_add",
                        "args": {"left": 17, "right": 25},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
                additional_kwargs={"reasoning_content": "private-provider-reasoning"},
            ),
            ToolMessage(content="42", tool_call_id="call-1", name="checked_add"),
            AIMessage(content=f"42 {secret}"),
        ],
        0.01,
    )
    evidence = turn_evidence(result, 0, secret)
    evidence["unexpected"] = secret
    path = save_evidence(settings, evidence)
    content = path.read_text()
    assert secret not in content
    assert "private-provider-reasoning" not in content
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(content)["unexpected"] == "[REDACTED]"
    assert verify_turn(result, 42, 0)


def test_smoke_does_not_pass_on_an_answer_without_tool_evidence() -> None:
    result = TurnResult("completed", "42", [AIMessage(content="42")], 0.01)
    assert not verify_turn(result, 42, 0)
    result = TurnResult("model_limit", "42", [], 0.01)
    assert not verify_turn(result, 42, 0)
