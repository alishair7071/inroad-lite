"""The one module that calls Olostep: search and scrape, with a time limit,
one retry, a cache and a running count of the credits spent. Mirrors
inroad-sourcing's app/net/olostep.py."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from inroad_lite.core.cache import Cache, NoCache, cache_key
from inroad_lite.sourcing.domain.olostep import (
    OlostepAuthError,
    OlostepRejected,
    OlostepUnavailable,
    OlostepUsage,
    SearchHit,
)

_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


class OlostepClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.olostep.com/v1",
        timeout_seconds: float = 60.0,
        cache: Cache | None = None,
        max_attempts: int = 2,
        max_concurrent: int = 4,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise OlostepAuthError("OLOSTEP_API_KEY is not set")
        if not base_url.startswith("https://"):
            raise OlostepRejected("Olostep base URL must be https")
        self.usage = OlostepUsage()
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._cache = cache or NoCache()
        self._max_attempts = max_attempts
        self._limit = asyncio.Semaphore(max_concurrent)
        self._sleep = sleep
        # No redirects and no proxies from the environment: either would see
        # the bearer token.
        self._http = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(timeout_seconds, connect=10.0),
            follow_redirects=False,
            trust_env=False,
        )

    async def __aenter__(self) -> OlostepClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def search(self, query: str) -> list[SearchHit]:
        body = await self._post("/searches", {"query": query})
        # result.json_content arrives as a JSON-encoded string.
        raw = (body.get("result") or {}).get("json_content")
        if not raw:
            return []
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            raise OlostepRejected("search returned malformed JSON") from None
        links = parsed.get("links", []) if isinstance(parsed, dict) else []
        return [
            SearchHit(
                url=link["url"],
                title=_text(link.get("title")),
                description=_text(link.get("description")),
            )
            for link in links
            if isinstance(link, dict) and isinstance(link.get("url"), str)
        ]

    async def scrape(self, url: str) -> str:
        """The page as markdown."""
        body = await self._post("/scrapes", {"url_to_scrape": url, "formats": ["markdown"]})
        markdown = (body.get("result") or {}).get("markdown_content")
        if not isinstance(markdown, str) or not markdown.strip():
            raise OlostepRejected("scrape returned no markdown")
        return markdown

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        key = cache_key(path, json.dumps(payload, sort_keys=True))
        cached = self._cache.get(key)
        if isinstance(cached, dict):
            self.usage.cache_hits += 1
            return cached
        async with self._limit:
            body = await self._post_with_retry(path, payload)
        self._cache.set(key, body)
        return body

    async def _post_with_retry(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        reason = "unknown"
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self._post_once(path, payload)
            except _Retryable as exc:
                reason = exc.reason
                if attempt < self._max_attempts:
                    await self._sleep(2.0 * attempt)
        self.usage.failures += 1
        operation = path.strip("/")
        raise OlostepUnavailable(f"{operation} failed after {self._max_attempts} tries: {reason}")

    async def _post_once(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.usage.calls += 1
        try:
            response = await self._http.post(
                f"{self._base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
            )
        except httpx.TimeoutException:
            raise _Retryable("timeout") from None
        except httpx.TransportError as exc:
            raise _Retryable(type(exc).__name__) from None

        status = response.status_code
        if status in _RETRYABLE_STATUSES:
            raise _Retryable(f"http {status}")
        if status in (401, 403):
            raise OlostepAuthError(f"Olostep refused the API key (http {status})")
        if not 200 <= status < 300:
            raise OlostepRejected(f"Olostep rejected the request (http {status})")
        try:
            body = response.json()
        except ValueError:
            raise OlostepRejected("response is not JSON") from None
        if not isinstance(body, dict):
            raise OlostepRejected("response is not a JSON object")
        credits = body.get("credits_consumed")
        if isinstance(credits, int):
            self.usage.credits += credits
        return body


class _Retryable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _text(value: object) -> str | None:
    return value.strip() or None if isinstance(value, str) else None
