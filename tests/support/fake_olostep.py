"""A scripted Olostep behind httpx.MockTransport: tests never need a key or
the network."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from inroad_lite.core.cache import Cache
from inroad_lite.sourcing.net.olostep import OlostepClient

KEY = "test-key-not-real"


def search_body(links: list[dict[str, str]], credits: int = 5) -> dict[str, object]:
    # json_content is a JSON-encoded string, as Olostep sends it.
    return {
        "id": "search_test",
        "object": "search",
        "credits_consumed": credits,
        "result": {"json_content": json.dumps({"links": links})},
    }


class FakeOlostep:
    def __init__(self, respond: Callable[[dict[str, object]], httpx.Response]) -> None:
        self.requests: list[dict[str, object]] = []
        self._respond = respond

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {KEY}"
        payload = json.loads(request.content)
        self.requests.append(payload)
        return self._respond(payload)

    def client(self, *, cache: Cache | None = None) -> OlostepClient:
        async def no_wait(_: float) -> None:
            return None

        return OlostepClient(
            api_key=KEY,
            cache=cache,
            transport=httpx.MockTransport(self.handler),
            sleep=no_wait,
        )
