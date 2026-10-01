import os

import pytest

from kestri.settings import Settings


def test_settings(**overrides: object) -> Settings:
    """Never load the owner's .env or credentials in offline tests."""
    values: dict[str, object] = {"DEEPSEEK_API_KEY": "test-only-placeholder", **overrides}
    return Settings(_env_file=None, **values)


test_settings.__test__ = False


@pytest.fixture(autouse=True)
def isolate_owner_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith("KESTRI_") or name in {
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_API_BASE",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        }:
            monkeypatch.delenv(name, raising=False)
