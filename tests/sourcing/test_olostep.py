from __future__ import annotations

import asyncio

import httpx
import pytest

from inroad_lite.core.cache import FileCache
from inroad_lite.sourcing.domain.olostep import OlostepAuthError, OlostepUnavailable
from tests.support.fake_olostep import KEY, FakeOlostep, search_body

LINK = {"url": "https://jobs.lever.co/acme/123", "title": "Acme - Backend Engineer"}


def run(coroutine):  # type: ignore[no-untyped-def]
    return asyncio.run(coroutine)


def test_a_search_reads_the_links_and_counts_credits():
    fake = FakeOlostep(lambda _: httpx.Response(200, json=search_body([LINK], credits=5)))

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            return await client.search("backend"), client.usage

    hits, usage = run(go())
    assert [hit.url for hit in hits] == [LINK["url"]]
    assert hits[0].title == "Acme - Backend Engineer"
    assert (usage.calls, usage.credits) == (1, 5)
    assert fake.requests == [{"query": "backend"}]


def test_a_timeout_is_tried_once_more_then_succeeds():
    answers = iter([httpx.ReadTimeout("slow"), httpx.Response(200, json=search_body([LINK]))])

    def respond(_: dict[str, object]) -> httpx.Response:
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    fake = FakeOlostep(respond)

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            return await client.search("backend"), client.usage

    hits, usage = run(go())
    assert len(hits) == 1
    assert usage.calls == 2


def test_two_timeouts_give_up_without_echoing_the_key():
    def respond(_: dict[str, object]) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    fake = FakeOlostep(respond)

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            await client.search("backend")

    with pytest.raises(OlostepUnavailable) as caught:
        run(go())
    assert "timeout" in str(caught.value)
    assert KEY not in str(caught.value)


def test_a_refused_key_is_not_retried():
    fake = FakeOlostep(lambda _: httpx.Response(401, json={"error": "bad key"}))

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            await client.search("backend")

    with pytest.raises(OlostepAuthError):
        run(go())
    assert len(fake.requests) == 1


def test_the_same_search_twice_is_answered_from_the_cache(tmp_path):
    fake = FakeOlostep(lambda _: httpx.Response(200, json=search_body([LINK], credits=5)))
    cache = FileCache(tmp_path, ttl_seconds=3600)

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client(cache=cache) as client:
            await client.search("backend")
            await client.search("backend")
            return client.usage

    usage = run(go())
    assert len(fake.requests) == 1
    assert (usage.credits, usage.cache_hits) == (5, 1)


def test_a_scrape_returns_the_page_as_markdown():
    body = {"credits_consumed": 1, "result": {"markdown_content": "# Acme\nWe build rockets."}}
    fake = FakeOlostep(lambda _: httpx.Response(200, json=body))

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            return await client.scrape("https://acme.com")

    assert run(go()).startswith("# Acme")
    assert fake.requests == [{"url_to_scrape": "https://acme.com", "formats": ["markdown"]}]
