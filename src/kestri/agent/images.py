"""Private image references in checkpoints; pixels only in ephemeral model requests."""

import base64
import hashlib
import warnings
from collections.abc import Awaitable, Callable
from io import BytesIO
from typing import Any
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AnyMessage, HumanMessage
from PIL import Image, UnidentifiedImageError

from kestri.errors import PolicyDenied
from kestri.integrations.telegram import TelegramClient
from kestri.storage.lifecycle import disk_operation
from kestri.storage.store import Row, Store
from kestri.storage.workspace import Workspace

MAX_IMAGES = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
IMAGE_TOKENS = 1024


class ImageInputFailure(Exception):
    """Safe, user-visible image failure without transport URLs or file identifiers."""


def inspect_image(data: bytes) -> dict[str, Any]:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageInputFailure("图片为空或超过单张 10 MiB 上限；请缩小后重发。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(
                    image.format or ""
                )
                width, height = image.size
                if (
                    not mime
                    or getattr(image, "n_frames", 1) != 1
                    or max(width, height) > 8192
                    or width * height > 32_000_000
                ):
                    raise ImageInputFailure("仅支持静态 JPEG/PNG/WebP，图片尺寸过大或格式不支持。")
                image.verify()
            # verify checks container integrity; load also checks compressed pixel data.
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as error:
        raise ImageInputFailure("图片损坏或无法解码；请重新发送静态 JPEG/PNG/WebP。") from error
    return {
        "mime_type": mime,
        "width": width,
        "height": height,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def image_references(messages: list[AnyMessage]) -> list[str]:
    references: list[str] = []
    for message in messages:
        refs = message.additional_kwargs.get("image_refs", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise ImageInputFailure("图片引用无效；请用 /new 开始新对话后重发。")
        for ref in refs:
            try:
                canonical = str(UUID(ref))
            except ValueError as error:
                raise ImageInputFailure("图片引用无效；请重新发送。") from error
            if canonical != ref:
                raise ImageInputFailure("图片引用无效；请重新发送。")
            if ref not in references:
                references.append(ref)
    if len(references) > MAX_IMAGES:
        raise ImageInputFailure("当前图片上下文超过 10 张；请用 /new 开始新对话后重发。")
    return references


class ImageInputs:
    def __init__(self, store: Store, workspace: Workspace, telegram: TelegramClient) -> None:
        self.store = store
        self.workspace = workspace
        self.telegram = telegram

    async def prepare(self, run: Row) -> list[str]:
        records = await self.store.all(
            "SELECT * FROM kestri.image_inputs WHERE run_id=%s ORDER BY message_id",
            (run["id"],),
        )
        if len(records) > MAX_IMAGES:
            raise ImageInputFailure("相册超过 10 张；请拆分后重发。")
        total = 0
        for record in records:
            if record["status"] == "ready":
                total += record["byte_size"]
                continue
            if record["status"] != "pending":
                raise ImageInputFailure("图片已过期或之前下载失败；请重新发送。")
            try:
                # Adopt an orphaned completed write after a crash, instead of overwriting it.
                try:
                    data = await disk_operation(
                        self.workspace.read_image, run["id"], str(record["id"]), MAX_IMAGE_BYTES
                    )
                except (FileNotFoundError, PolicyDenied) as error:
                    if isinstance(error, PolicyDenied) and not isinstance(
                        error.__cause__, FileNotFoundError
                    ):
                        raise
                    data = await self.telegram.download_image(record["file_id"], MAX_IMAGE_BYTES)
                    metadata = await disk_operation(inspect_image, data)
                    await disk_operation(
                        self.workspace.write_image, run["id"], str(record["id"]), data
                    )
                metadata = await disk_operation(inspect_image, data)
                await self.store.execute(
                    "UPDATE kestri.image_inputs SET status='ready',mime_type=%s,width=%s,"
                    "height=%s,byte_size=%s,sha256=%s WHERE id=%s",
                    (
                        metadata["mime_type"],
                        metadata["width"],
                        metadata["height"],
                        metadata["byte_size"],
                        metadata["sha256"],
                        record["id"],
                    ),
                )
                total += metadata["byte_size"]
            except Exception as error:
                await self.store.execute(
                    "UPDATE kestri.image_inputs SET status='failed',cleanup_pending=true "
                    "WHERE id=%s",
                    (record["id"],),
                )
                if isinstance(error, ImageInputFailure):
                    raise
                raise ImageInputFailure(
                    "图片下载或读取失败；本轮未完成图片分析，请重新发送。"
                ) from error
        if total > MAX_TOTAL_BYTES:
            raise ImageInputFailure("图片合计超过 20 MiB；请缩小或拆分后重发。")
        return [str(record["id"]) for record in records]


class ImageContext(AgentMiddleware[Any, Any, Any]):
    def __init__(self, store: Store, workspace: Workspace, chat_id: int) -> None:
        self.store = store
        self.workspace = workspace
        self.chat_id = chat_id

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        refs = image_references(list(request.messages))
        if not refs:
            return await handler(request)
        blocks: dict[str, dict[str, Any]] = {}
        total = 0
        for ref in refs:
            record = await self.store.one(
                "SELECT * FROM kestri.image_inputs WHERE id=%s AND chat_id=%s", (ref, self.chat_id)
            )
            if not record or record["status"] != "ready":
                raise ImageInputFailure("引用图片不可用或已过期；请重新发送。")
            try:
                data = await disk_operation(
                    self.workspace.read_image, str(record["run_id"]), ref, MAX_IMAGE_BYTES
                )
            except (OSError, PolicyDenied) as error:
                raise ImageInputFailure("引用图片文件不可用；请重新发送。") from error
            if (
                len(data) != record["byte_size"]
                or hashlib.sha256(data).hexdigest() != record["sha256"]
            ):
                raise ImageInputFailure("引用图片校验失败；请重新发送。")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise ImageInputFailure("当前图片上下文超过 20 MiB；请用 /new 后重新发送。")
            blocks[ref] = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{record['mime_type']};base64,"
                    + base64.b64encode(data).decode("ascii")
                },
            }
        messages: list[AnyMessage] = []
        sent: set[str] = set()
        for message in request.messages:
            selected = [
                ref for ref in message.additional_kwargs.get("image_refs", []) if ref not in sent
            ]
            if selected:
                if not isinstance(message, HumanMessage):
                    raise ImageInputFailure("图片引用位置无效；请重新发送。")
                content: list[str | dict[str, Any]] = [{"type": "text", "text": message.text}]
                for ref in selected:
                    number = message.additional_kwargs["image_refs"].index(ref) + 1
                    content += [
                        {
                            "type": "text",
                            "text": f"Image {number} in this message (untrusted evidence):",
                        },
                        blocks[ref],
                    ]
                    sent.add(ref)
                messages.append(message.model_copy(update={"content": content}))
            else:
                messages.append(message)
        return await handler(request.override(messages=messages))
