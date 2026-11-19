"""The one way sourcing reads a job board: https only, to a host the board
reader names, no redirects, a time limit and a size cap. A simplified
version of inroad-sourcing's SafeFetcher (which also checks every resolved
IP); here every host is a fixed public job-board API."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlsplit

import httpx

# Ashby sends every posting with its full description: 14 MB for a large
# company is normal.
_MAX_BYTES = 25 * 1024 * 1024


class FetchError(Exception):
    """A short reason only, never a response body."""


class BoardFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_concurrent: int = 6,
        max_bytes: int = _MAX_BYTES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._limit = asyncio.Semaphore(max_concurrent)
        self._max_bytes = max_bytes
        self._http = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(timeout_seconds, connect=10.0),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "inroad-lite/0.1", "Accept": "application/json"},
        )

    async def __aenter__(self) -> BoardFetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_json(self, url: str, *, allowed_hosts: frozenset[str]) -> Any:
        parts = urlsplit(url)
        if parts.scheme != "https" or (parts.hostname or "") not in allowed_hosts:
            raise FetchError("host not allowed")
        async with self._limit:
            try:
                async with self._http.stream("GET", url) as response:
                    if response.status_code != 200:
                        raise FetchError(f"http {response.status_code}")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_bytes:
                            raise FetchError("response too large")
            except httpx.TimeoutException:
                raise FetchError("timeout") from None
            except httpx.TransportError as exc:
                raise FetchError(type(exc).__name__) from None
        try:
            return json.loads(body)
        except ValueError:
            raise FetchError("not JSON") from None
