"""Narrow compatibility adapter for DeepSeek's assistant-message contract."""

from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_deepseek import ChatDeepSeek


class DeepSeekChatModel(ChatDeepSeek):
    """Preserve provider reasoning across tool calls and later conversation turns.

    langchain-deepseek 1.1.1 reads reasoning_content but its inherited outbound
    serializer omits it. Keep this private SDK hook isolated and regression-tested.
    """

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        originals = self._convert_input(input_).to_messages()
        for original, message in zip(originals, payload["messages"], strict=True):
            if isinstance(original, AIMessage):
                reasoning = original.additional_kwargs.get("reasoning_content")
                if isinstance(reasoning, str):
                    message["reasoning_content"] = reasoning
                if message.get("content") is None:
                    message["content"] = ""
        return payload
