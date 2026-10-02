import asyncio
from typing import Any

import httpx
import pytest
from langchain_core.messages import ToolMessage
from langchain_deepseek import ChatDeepSeek

from kestri.runtime import AgentSession, build_model
from kestri.smoke import verify_turn

from .conftest import test_settings
from .helpers import completion, offline_model, tool_call


async def test_real_agent_loop_preserves_tool_result_and_followup() -> None:
    requests: list[dict[str, Any]] = []
    model, async_client, sync_client = offline_model(
        [
            tool_call(17, 25),
            {"role": "assistant", "content": "42"},
            tool_call(42, 8, "call-2"),
            {"role": "assistant", "content": "50"},
        ],
        requests,
    )
    session = AgentSession(test_settings(), model)
    try:
        first = await session.ask("Add 17 and 25.")
        second = await session.ask("Add 8 to the previous result.")
        assert verify_turn(first, 42, 0)
        assert verify_turn(second, 50, len(first.messages))
        assert any(
            msg["role"] == "tool" and msg["content"] == "42" for msg in requests[1]["messages"]
        )
        assert any(
            msg["role"] == "tool" and msg["content"] == "42" for msg in requests[2]["messages"]
        )
        assert len(requests) == 4
        assistant = requests[1]["messages"][-2]
        assert assistant["content"] == ""
        assert "reasoning_content" not in assistant
    finally:
        await session.aclose()
        await async_client.aclose()
        sync_client.close()


async def test_thinking_content_is_replayed_without_exporting_it() -> None:
    requests: list[dict[str, Any]] = []
    first_call = {**tool_call(17, 25), "reasoning_content": "first-tool-reasoning"}
    first_answer = {
        "role": "assistant",
        "content": "42",
        "reasoning_content": "first-answer-reasoning",
    }
    model, async_client, sync_client = offline_model(
        [
            first_call,
            first_answer,
            tool_call(42, 8, "call-2"),
            {"role": "assistant", "content": "50"},
        ],
        requests,
    )
    session = AgentSession(test_settings(thinking_mode="enabled"), model)
    try:
        first = await session.ask("Add 17 and 25.")
        second = await session.ask("Add 8 to the previous result.")
        assert verify_turn(first, 42, 0)
        assert verify_turn(second, 50, len(first.messages))
        assert requests[1]["messages"][-2].get("reasoning_content") == "first-tool-reasoning"
        previous_assistants = [
            message for message in requests[2]["messages"] if message["role"] == "assistant"
        ]
        assert previous_assistants[0].get("reasoning_content") == "first-tool-reasoning"
        assert previous_assistants[1].get("reasoning_content") == "first-answer-reasoning"
    finally:
        await session.aclose()
        await async_client.aclose()
        sync_client.close()


@pytest.mark.parametrize("limit", ["model", "tool"])
async def test_call_limits_stop_an_actual_agent_loop(limit: str) -> None:
    requests: list[dict[str, Any]] = []
    responses = [tool_call(1, 2), tool_call(3, 4, "call-2")]
    model, async_client, sync_client = offline_model(responses, requests)
    research_settings = test_settings(**{f"max_{limit}_calls": 1})
    session = AgentSession(research_settings, model)
    try:
        result = await session.ask("Keep adding.")
        assert result.status == f"{limit}_limit"
        assert len(requests) == (1 if limit == "model" else 2)
        with pytest.raises(RuntimeError, match="new session"):
            await session.ask("Continue")
        assert len(requests) == (1 if limit == "model" else 2)
    finally:
        await session.aclose()
        await async_client.aclose()
        sync_client.close()


async def test_tool_failure_is_safely_returned_to_model() -> None:
    requests: list[dict[str, Any]] = []
    model, async_client, sync_client = offline_model(
        [
            tool_call(1_000_000, 1),
            {"role": "assistant", "content": "Outside the tool range."},
        ],
        requests,
    )
    session = AgentSession(test_settings(), model)
    try:
        result = await session.ask("Add numbers outside the total range.")
        assert result.status == "completed"
        assert any(
            isinstance(msg, ToolMessage) and msg.status == "error" for msg in result.messages
        )
        assert "permitted range" in requests[1]["messages"][-1]["content"]
    finally:
        await session.aclose()
        await async_client.aclose()
        sync_client.close()


async def test_timeout_cancels_inflight_work() -> None:
    requests: list[httpx.Request] = []

    async def slow(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        await asyncio.sleep(10)
        return httpx.Response(200, json=completion({"role": "assistant", "content": "late"}))

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(slow))
    model = ChatDeepSeek(
        model="deepseek-flash",
        api_key=test_settings().deepseek_api_key,
        http_async_client=async_client,
        max_retries=0,
    )
    session = AgentSession(test_settings(run_timeout_seconds=0.05), model)
    try:
        result = await session.ask("Wait")
        assert result.status == "timeout"
        assert len(requests) == 1
        assert result.elapsed_seconds < 1
    finally:
        await session.aclose()
        await async_client.aclose()


async def test_provider_failure_does_not_surface_response_body() -> None:
    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                401, json={"error": {"message": "sensitive-response-body"}}
            )
        )
    )
    model = ChatDeepSeek(
        model="deepseek-flash",
        api_key=test_settings().deepseek_api_key,
        http_async_client=async_client,
        max_retries=0,
    )
    session = AgentSession(test_settings(), model)
    try:
        result = await session.ask("Hello")
        assert result.status == "provider_error"
        assert result.error_type in {"AuthenticationError", "OpenAIAuthenticationError"}
        assert "sensitive-response-body" not in repr(result)
        assert result.answer == ""
    finally:
        await session.aclose()
        await async_client.aclose()


async def test_official_endpoint_and_mode_override_ambient_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_BASE", "https://untrusted.invalid")
    model = build_model(test_settings(thinking_mode="enabled"))
    assert model.api_base == "https://api.deepseek.com/v1"
    assert model.extra_body == {"thinking": {"type": "enabled"}}
    assert model.max_retries == 0
    await model.root_async_client.close()
    model.root_client.close()


async def test_explicit_cancellation_is_not_swallowed() -> None:
    entered = asyncio.Event()

    async def wait_forever(request: httpx.Request) -> httpx.Response:
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(wait_forever))
    model = ChatDeepSeek(
        model="deepseek-flash",
        api_key=test_settings().deepseek_api_key,
        http_async_client=async_client,
        max_retries=0,
    )
    session = AgentSession(test_settings(), model)
    try:
        task = asyncio.create_task(session.ask("Wait"))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(RuntimeError, match="new session"):
            await session.ask("Continue")
    finally:
        await session.aclose()
        await async_client.aclose()
