import pytest
from pydantic import ValidationError

from kestri.settings import Settings

from .conftest import test_settings


def test_missing_or_empty_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    with pytest.raises(ValidationError):
        test_settings(DEEPSEEK_API_KEY="   ")


@pytest.mark.parametrize(
    "value",
    [{"max_model_calls": 0}, {"max_tool_calls": 21}, {"run_timeout_seconds": -1}],
)
def test_invalid_limits_are_rejected(value: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        test_settings(**value)


def test_secret_is_not_in_settings_repr() -> None:
    research_settings = test_settings()
    assert research_settings.deepseek_api_key.get_secret_value() not in repr(research_settings)
