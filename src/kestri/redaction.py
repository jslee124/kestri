"""Redact configured credentials at every user-visible persistence boundary."""

import json
from typing import Any


class Redactor:
    def __init__(self, secrets: list[str]) -> None:
        self._secrets = tuple(value for value in secrets if value)

    def text(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, "[REDACTED]")
        return value

    def data(self, value: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(self.text(json.dumps(value, ensure_ascii=False)))
        return result
