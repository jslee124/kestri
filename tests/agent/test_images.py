import base64
from io import BytesIO
from uuid import uuid4

import httpx
import pytest
from langchain_core.messages import HumanMessage
from PIL import Image

from kestri.agent.budget import conservative_input_size
from kestri.agent.images import MAX_IMAGE_BYTES, ImageInputFailure, image_references, inspect_image
from kestri.errors import PolicyDenied, ProviderFailure
from kestri.integrations.telegram import TelegramClient, authorized_message, image_file_id
from kestri.storage.workspace import Workspace
from tests.helpers import offline_model, telegram_update


def image_bytes(color: str = "red", format: str = "PNG") -> bytes:
    stream = BytesIO()
    Image.new("RGB", (16, 12), color).save(stream, format=format)
    return stream.getvalue()


def photo_update(identity: int = 1, caption: str = "", group: str | None = None) -> dict:
    update = telegram_update(update_id=identity, message_id=identity)
    message = update["message"]
    del message["text"]
    message["photo"] = [
        {"file_id": "thumbnail", "width": 4, "height": 3},
        {"file_id": f"photo-{identity}", "width": 16, "height": 12},
    ]
    message["caption"] = caption
    if group:
        message["media_group_id"] = group
    return update


def test_photo_sizes_are_one_image_and_authorization_is_unchanged() -> None:
    update = photo_update(caption="说明")
    assert image_file_id(update["message"]) == "photo-1"
    assert authorized_message(update, 111)["text"] == "说明"
    assert authorized_message(update, 222) is None
    update["message"]["chat"]["type"] = "group"
    assert authorized_message(update, 111) is None


def test_image_documents_use_captions_and_nonimages_are_ignored() -> None:
    update = photo_update()
    del update["message"]["photo"]
    update["message"]["document"] = {"file_id": "file", "mime_type": "image/png"}
    assert authorized_message(update, 111)["text"] == ""
    update["message"]["document"]["mime_type"] = "application/pdf"
    assert authorized_message(update, 111) is None


@pytest.mark.parametrize(
    "format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_actual_image_format_and_dimensions_are_verified(format: str, mime: str) -> None:
    result = inspect_image(image_bytes(format=format))
    assert result["mime_type"] == mime and result["width"] == 16 and result["height"] == 12


def test_invalid_animated_oversized_and_truncated_images_are_rejected() -> None:
    for data in (b"not pixels", b"", b"x" * (MAX_IMAGE_BYTES + 1), image_bytes()[:50]):
        with pytest.raises(ImageInputFailure):
            inspect_image(data)
    stream = BytesIO()
    Image.new("RGB", (2, 2), "red").save(
        stream, format="PNG", save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")]
    )
    with pytest.raises(ImageInputFailure):
        inspect_image(stream.getvalue())
    stream = BytesIO()
    Image.new("RGB", (8193, 1)).save(stream, format="PNG")
    with pytest.raises(ImageInputFailure):
        inspect_image(stream.getvalue())


def test_image_reference_budget_counts_pixels_without_base64() -> None:
    text = HumanMessage(content="compare")
    refs = [str(uuid4()), str(uuid4())]
    images = HumanMessage(content="compare", additional_kwargs={"image_refs": refs})
    assert conservative_input_size([images], []) - conservative_input_size([text], []) >= 2048
    assert image_references([images, images]) == refs
    with pytest.raises(ImageInputFailure):
        image_references([HumanMessage(content="", additional_kwargs={"image_refs": ["../x"]})])
    with pytest.raises(ImageInputFailure):
        image_references(
            [
                HumanMessage(
                    content="", additional_kwargs={"image_refs": [str(uuid4()) for _ in range(11)]}
                )
            ]
        )


async def test_locked_deepseek_adapter_sends_multiple_image_blocks() -> None:
    requests = []
    model, async_client, sync_client = offline_model(
        [{"role": "assistant", "content": "ok"}], requests
    )
    data = base64.b64encode(image_bytes()).decode("ascii")
    try:
        await model.ainvoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": "compare"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64," + data},
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64," + data},
                        },
                    ]
                )
            ]
        )
    finally:
        await async_client.aclose()
        sync_client.close()
    assert [block["type"] for block in requests[0]["messages"][0]["content"]] == [
        "text",
        "image_url",
        "image_url",
    ]


@pytest.mark.parametrize(
    "path", ["../secret.png", "/photo.png", "https://evil/photo.png", "photos/a.png?token=x"]
)
async def test_download_rejects_unsafe_paths_before_fetch(path: str) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"file_path": path}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ProviderFailure):
            await TelegramClient("123:secret", client).download_image("file", 100)
    assert len(requests) == 1


async def test_download_bounds_actual_bytes_and_does_not_follow_redirects() -> None:
    for status, body in [(200, b"x" * 101), (302, b"")]:

        def respond(
            request: httpx.Request, status: int = status, body: bytes = body
        ) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    200, json={"ok": True, "result": {"file_path": "photos/a.png"}}
                )
            return httpx.Response(status, content=body, headers={"location": "https://evil/"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with pytest.raises(ProviderFailure):
                await TelegramClient("123:secret", client).download_image("file", 100)


def test_image_files_are_private_and_symlinks_cannot_escape(tmp_path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    run_id, image_id = str(uuid4()), str(uuid4())
    data = image_bytes()
    workspace.write_image(run_id, image_id, data)
    path = workspace.root / run_id / f"{image_id}.image"
    assert path.stat().st_mode & 0o777 == 0o600
    assert workspace.read_image(run_id, image_id, MAX_IMAGE_BYTES) == data
    path.unlink()
    external = tmp_path / "external"
    external.write_bytes(data)
    path.symlink_to(external)
    with pytest.raises(PolicyDenied):
        workspace.read_image(run_id, image_id, MAX_IMAGE_BYTES)
    workspace.remove_image(run_id, image_id)
    assert external.exists()
