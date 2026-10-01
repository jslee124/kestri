"""Validate public URL targets before delegating retrieval to a provider."""

import asyncio
import ipaddress
import json
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx

from kestri.errors import PolicyDenied

Resolver = Callable[[str, int], Awaitable[list[str]]]


async def resolve_host(host: str, port: int) -> list[str]:
    async with asyncio.timeout(3):
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    return list({address[4][0] for address in addresses})


class CloudflareResolver:
    """Opt-in public DNS checks for remotely fetched URLs; never forward service secrets."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def __call__(self, host: str, port: int) -> list[str]:
        async def query(record_type: int) -> list[str]:
            async with self.client.stream(
                "GET",
                "https://cloudflare-dns.com/dns-query",
                params={"name": host, "type": record_type},
                headers={"Accept": "application/dns-json"},
            ) as response:
                if response.status_code != 200:
                    raise ValueError("DNSUnavailable")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 65536:
                        raise ValueError("DNSResponseTooLarge")
            data = json.loads(body)
            if not isinstance(data, dict) or data.get("Status") != 0 or data.get("TC"):
                raise ValueError("DNSInvalid")
            answers = data.get("Answer", [])
            if not isinstance(answers, list):
                raise ValueError("DNSInvalid")
            return [str(item["data"]) for item in answers if item.get("type") in {1, 28}]

        try:
            async with asyncio.timeout(6):
                ipv4, ipv6 = await asyncio.gather(query(1), query(28))
            return list(set(ipv4 + ipv6))
        except (httpx.HTTPError, KeyError, TypeError, UnicodeError) as error:
            raise ValueError("DNSUnavailable") from error


class PublicURLPolicy:
    def __init__(self, resolver: Resolver = resolve_host) -> None:
        self.resolver = resolver

    async def validate(self, url: str) -> str:
        if len(url) > 2048 or any(ord(char) < 33 for char in url) or "\\" in url:
            raise PolicyDenied("InvalidURL")
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as error:
            raise PolicyDenied("InvalidURL") from error
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or port not in {80, 443}
            or host.rstrip(".")
            .lower()
            .endswith(("localhost", ".local", ".internal", ".lan", ".localhost"))
            or any(
                key.lower() in {"token", "api_key", "apikey", "password", "secret", "access_token"}
                for key, _ in parse_qsl(parsed.query)
            )
        ):
            raise PolicyDenied("NonPublicURL")
        try:
            try:
                literal = ipaddress.ip_address(host)
            except ValueError:
                addresses = await self.resolver(host, port)
            else:
                addresses = [str(literal)]
            if not addresses:
                raise ValueError("Unresolved")
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if not ip.is_global or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped):
                    raise ValueError("NonPublic")
        except (OSError, ValueError, TimeoutError) as error:
            raise PolicyDenied("NonPublicOrUnresolvedURL") from error
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
