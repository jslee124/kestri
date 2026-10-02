import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from kestri.embedding import EmbeddingClient, save_embedding_evidence
from kestri.errors import PolicyDenied, ProviderFailure
from kestri.settings import EmbeddingSettings


def settings(**overrides: Any) -> EmbeddingSettings:
    values = {
        "DASHSCOPE_API_KEY": "test-embedding-secret",
        "embedding_base_url": "https://llm-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "embedding_dimensions": 64,
        **overrides,
    }
    return EmbeddingSettings(_env_file=None, **values)


def response() -> dict[str, Any]:
    return {
        "model": "text-embedding-v4",
        "data": [
            {"index": 1, "embedding": [0.2] * 64},
            {"index": 0, "embedding": [0.1] * 64},
        ],
        "usage": {"prompt_tokens": 20, "total_tokens": 20},
    }


async def test_request_and_reordered_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/compatible-mode/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer test-embedding-secret"
        assert json.loads(request.content) == {
            "model": "text-embedding-v4",
            "input": ["目标", "问题"],
            "dimensions": 64,
            "encoding_format": "float",
        }
        return httpx.Response(200, json=response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await EmbeddingClient(settings(), http).embed(["目标", "问题"])
    assert result.vectors[0] == (0.1,) * 64
    assert result.vectors[1] == (0.2,) * 64
    assert result.input_tokens == 20


@pytest.mark.parametrize(
    "case", ["dimension", "nan", "bool", "zero", "index", "usage", "model", "huge"]
)
async def test_rejects_invalid_provider_output(case: str) -> None:
    payload = response()
    if case == "dimension":
        payload["data"][0]["embedding"].pop()
    elif case == "nan":
        payload["data"][0]["embedding"][0] = float("nan")
    elif case == "bool":
        payload["data"][0]["embedding"][0] = True
    elif case == "huge":
        payload["data"][0]["embedding"][0] = 10**500
    elif case == "zero":
        payload["data"][0]["embedding"] = [0] * 64
    elif case == "index":
        payload["data"][0]["index"] = 0
    elif case == "usage":
        payload["usage"]["prompt_tokens"] = -1
    else:
        payload["model"] = "different-model"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=json.dumps(payload))
    )
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ProviderFailure):
            await EmbeddingClient(settings(), http).embed(["目标", "问题"])


@pytest.mark.parametrize("texts", [[], [" "], ["中" * 3000], ["a"] * 11, ["test-embedding-secret"]])
async def test_input_rejected_before_network(texts: list[str]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("Input rejection must precede network access")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(PolicyDenied):
            await EmbeddingClient(settings(), http).embed(texts)


async def test_redirect_does_not_forward_credentials() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(307, headers={"Location": "https://untrusted.example/"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as http:
        with pytest.raises(ProviderFailure, match="HTTP_307"):
            await EmbeddingClient(settings(), http).embed(["目标"])
    assert calls == 1


async def test_http_failure_suppresses_private_body() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, text="test-embedding-secret private input")
    )
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ProviderFailure) as error:
            await EmbeddingClient(settings(), http).embed(["目标"])
    assert str(error.value) == "HTTP_401"


@pytest.mark.parametrize(
    "url",
    [
        "http://llm-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "https://untrusted.example/compatible-mode/v1",
        "https://llm-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1?key=x",
        "https://user@llm-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "https://llm-test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    ],
)
def test_endpoint_restricted_to_beijing(url: str) -> None:
    with pytest.raises(ValidationError):
        settings(embedding_base_url=url)


def test_environment_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KESTRI_EMBEDDING_DIMENSIONS", "1024")
    config = EmbeddingSettings(
        _env_file=None,
        DASHSCOPE_API_KEY="test-embedding-secret",
        embedding_base_url="https://llm-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    )
    assert config.embedding_dimensions == 1024


async def test_transport_failure_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private details test-embedding-secret", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ProviderFailure, match="^EmbeddingTransportFailure$"):
            await EmbeddingClient(settings(), http).embed(["目标"])


async def test_oversized_response_is_rejected() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 2_000_001))
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ProviderFailure, match="ResponseTooLarge"):
            await EmbeddingClient(settings(), http).embed(["目标"])


def test_independent_settings_and_safe_evidence(tmp_path: Path) -> None:
    config = settings(embedding_evidence_dir=tmp_path)
    assert "test-embedding-secret" not in repr(config)
    evidence = {"model": config.embedding_model, "passed": True}
    path = save_embedding_evidence(config, evidence)
    assert json.loads(path.read_text()) == evidence
    assert "test-embedding-secret" not in path.read_text()
