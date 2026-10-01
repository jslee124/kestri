import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from kestri.errors import PolicyDenied, ProviderFailure
from kestri.http import post_json
from kestri.telegram import DeliveryProblem, TelegramClient, authorized_message, command_for
from kestri.url_policy import PublicURLPolicy
from kestri.workspace import Workspace


async def public(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


async def private(host: str, port: int) -> list[str]:
    return ["127.0.0.1"]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/admin",
        "http://service.internal/",
        "http://user:password@example.com/",
        "https://example.com:9000/",
        "https://example.com/?api_key=secret",
        "http://example.com/\\evil",
        "http://example.com/\nheader",
    ],
)
async def test_url_rejects_unsupported_targets_before_provider_work(url: str) -> None:
    with pytest.raises(PolicyDenied):
        await PublicURLPolicy(public).validate(url)


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1", "::ffff:8.8.8.8", "0.0.0.0"],
)
async def test_url_rejects_nonpublic_dns_and_address_forms(ip: str) -> None:
    async def resolve(host: str, port: int) -> list[str]:
        return [ip]

    with pytest.raises(PolicyDenied):
        await PublicURLPolicy(resolve).validate("https://example.com/")


async def test_url_accepts_public_target_and_removes_fragment() -> None:
    assert (
        await PublicURLPolicy(public).validate("https://example.com/page#part")
        == "https://example.com/page"
    )


def test_workspace_rejects_run_and_file_symlinks(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    run_id, evidence_id = str(uuid4()), str(uuid4())
    original = tmp_path / "original"
    original.write_text("protected")
    (workspace.root / run_id).symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PolicyDenied):
        workspace.write(run_id, evidence_id, "overwrite")
    (workspace.root / run_id).unlink()
    (workspace.root / run_id).mkdir()
    (workspace.root / run_id / f"{evidence_id}.txt").symlink_to(original)
    with pytest.raises(PolicyDenied):
        workspace.read(run_id, evidence_id, 100)
    assert original.read_text() == "protected"


def test_workspace_returns_bounded_content(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    run_id, evidence_id = str(uuid4()), str(uuid4())
    workspace.write(run_id, evidence_id, "a" * 100)
    assert workspace.read(run_id, evidence_id, 10) == ("a" * 10, True)
    with pytest.raises(ValueError):
        workspace.read(run_id, "../../original", 10)


async def test_bounded_provider_json_read() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"text": "a" * 1000})
        )
    ) as client:
        with pytest.raises(ProviderFailure, match="ResponseTooLarge"):
            await post_json(client, "https://provider.invalid", {}, max_bytes=100)


def update(
    text: str = "Research this",
    user_id: int = 111,
    chat_type: str = "private",
    update_id: int = 1,
    message_id: int = 1,
    reply_to: int | None = None,
) -> dict:
    message = {
        "message_id": message_id,
        "text": text,
        "from": {"id": user_id, "is_bot": False},
        "chat": {"id": user_id, "type": chat_type},
    }
    if reply_to is not None:
        message["reply_to_message"] = {"message_id": reply_to}
    return {"update_id": update_id, "message": message}


@pytest.mark.parametrize("user,chat", [(222, "private"), (111, "group"), (111, "channel")])
def test_owner_and_private_chat_are_both_required(user: int, chat: str) -> None:
    assert authorized_message(update(user_id=user, chat_type=chat), 111) is None


async def test_telegram_rate_limit_is_known_rejection_and_timeout_is_uncertain() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "parameters": {"retry_after": 5},
                },
            )
        )
    ) as client:
        telegram = TelegramClient("123:placeholder", client)
        with pytest.raises(DeliveryProblem) as info:
            await telegram.send(111, "result")
        assert not info.value.uncertain and info.value.delay == 5

    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive transport details", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(DeliveryProblem) as info:
            await TelegramClient("123:placeholder", client).send(111, "result")
        assert info.value.uncertain
        assert "sensitive transport details" not in str(info.value)


async def test_telegram_invalid_success_response_is_uncertain() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"unexpected": "data"})
        )
    ) as client:
        with pytest.raises(DeliveryProblem) as info:
            await TelegramClient("123:placeholder", client).send(111, "result")
        assert info.value.uncertain


async def test_telegram_sends_plain_bounded_message_without_link_preview() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 100}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert (
            await TelegramClient("123:placeholder", client).send(111, "<script>data</script>", 1)
            == 100
        )
    assert "parse_mode" not in requests[0]
    assert requests[0]["link_preview_options"]["is_disabled"]
    assert requests[0]["reply_markup"] == {"remove_keyboard": True}


async def test_native_menu_exposes_all_commands_to_owner_in_both_languages() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await TelegramClient("123:placeholder", client).configure_menu(111)
    for method, payload in requests[:2]:
        assert method == "setMyCommands"
        assert payload["scope"] == {"type": "chat", "chat_id": 111}
        commands = payload["commands"]
        assert {item["command"] for item in commands} == {
            "start",
            "status",
            "runs",
            "usage",
            "stop",
            "new",
            "help",
        }
        for item in commands:
            text = "/" + item["command"]
            assert item["description"]
            assert command_for(text) == item["command"]
            assert authorized_message(update(text=text, user_id=222), 111) is None
    assert [payload["language_code"] for _, payload in requests[:2]] == ["", "zh"]
    assert requests[2] == (
        "setChatMenuButton",
        {"chat_id": 111, "menu_button": {"type": "commands"}},
    )


async def test_opt_in_doh_verifies_public_records_and_rejects_private_records() -> None:
    from kestri.url_policy import CloudflareResolver

    requests = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        value = "93.184.216.34" if request.url.params["name"] == "example.com" else "10.0.0.1"
        records = [{"type": 1, "data": value}] if request.url.params["type"] == "1" else []
        return httpx.Response(200, json={"Status": 0, "Answer": records})

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        policy = PublicURLPolicy(CloudflareResolver(client))
        assert await policy.validate("https://example.com/fact") == "https://example.com/fact"
        with pytest.raises(PolicyDenied):
            await policy.validate("https://private.example.com/secret")
        before = len(requests)
        with pytest.raises(PolicyDenied):
            await policy.validate("http://127.0.0.1/private")
        assert len(requests) == before
    assert len(requests) == 4
    assert all(request.url.host == "cloudflare-dns.com" for request in requests)
    assert all("authorization" not in request.headers for request in requests)


async def test_doh_failure_never_falls_back_to_system_resolution() -> None:
    from kestri.url_policy import CloudflareResolver

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"Status": 3}))
    ) as client:
        with pytest.raises(PolicyDenied):
            await PublicURLPolicy(CloudflareResolver(client)).validate("https://example.com")
