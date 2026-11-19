from __future__ import annotations

import asyncio

import httpx
import pytest

from inroad_lite.sourcing.net.fetcher import BoardFetcher, FetchError

ALLOWED = frozenset({"api.lever.co"})
URL = "https://api.lever.co/v0/postings/acme?mode=json"


def fetch(handler, url: str = URL, **options: object):  # type: ignore[no-untyped-def]
    sent: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return handler(request)

    async def go():  # type: ignore[no-untyped-def]
        transport = httpx.MockTransport(record)
        async with BoardFetcher(transport=transport, **options) as fetcher:  # type: ignore[arg-type]
            return await fetcher.get_json(url, allowed_hosts=ALLOWED)

    return asyncio.run(go()), sent


def test_a_board_answer_is_read_as_json():
    result, _ = fetch(lambda _: httpx.Response(200, json=[{"id": "a"}]))
    assert result == [{"id": "a"}]


def test_a_host_the_reader_did_not_name_is_never_contacted():
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(200, json=[])

    with pytest.raises(FetchError, match="host not allowed"):
        fetch(handler, url="https://evil.example/v0/postings/acme")
    with pytest.raises(FetchError, match="host not allowed"):
        fetch(handler, url="http://api.lever.co/v0/postings/acme")
    assert sent == []


def test_redirects_are_not_followed():
    with pytest.raises(FetchError, match="http 302"):
        fetch(lambda _: httpx.Response(302, headers={"location": "https://elsewhere.example"}))


def test_an_oversized_answer_is_refused():
    with pytest.raises(FetchError, match="too large"):
        fetch(lambda _: httpx.Response(200, content=b"x" * 2048), max_bytes=1024)


def test_an_answer_that_is_not_json_is_refused():
    with pytest.raises(FetchError, match="not JSON"):
        fetch(lambda _: httpx.Response(200, content=b"<html>"))
