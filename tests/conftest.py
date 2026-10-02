import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import pytest

from kestri.redaction import Redactor
from kestri.settings import Settings
from kestri.store import Store

TEST_DSN = os.environ.get("KESTRI_TEST_DATABASE_URL")


def test_settings(**overrides: object) -> Settings:
    """Never load the owner's .env or credentials in offline tests."""
    values: dict[str, object] = {
        "DEEPSEEK_API_KEY": "test-only-placeholder",
        **overrides,
    }
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


@pytest.fixture
async def store() -> AsyncIterator[Store]:
    if not TEST_DSN:
        pytest.skip("Set a dedicated KESTRI_TEST_DATABASE_URL")
    parsed = urlsplit(TEST_DSN or "")
    assert parsed.hostname in {"127.0.0.1", "localhost"} and parsed.path == "/kestri_test"
    repository = Store(TEST_DSN, Redactor(["test-only-placeholder", "test-tavily-placeholder"]))
    await repository.pool.open(wait=True)
    await repository.execute("DROP SCHEMA IF EXISTS kestri CASCADE")
    await repository.open()
    try:
        yield repository
    finally:
        await repository.close()
