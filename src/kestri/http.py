"""Bounded JSON reads over injected HTTP transports."""

import json
from typing import Any

import httpx

from kestri.errors import ProviderFailure


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    *,
    max_bytes: int = 2_000_000,
    allow_error_json: bool = False,
) -> dict[str, Any]:
    async with client.stream("POST", url, json=payload) as response:
        if response.status_code != 200 and not (
            allow_error_json and response.status_code in {400, 401, 403, 409, 429, 500, 502, 503}
        ):
            raise ProviderFailure(f"HTTP_{response.status_code}")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ProviderFailure("ResponseTooLarge")
    try:
        result = json.loads(body)
    except (ValueError, UnicodeError) as error:
        raise ProviderFailure("InvalidResponse") from error
    if not isinstance(result, dict):
        raise ProviderFailure("InvalidResponse")
    return result
