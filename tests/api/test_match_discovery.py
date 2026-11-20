from __future__ import annotations

import asyncio

import httpx
import pytest

from inroad_lite.api.routers import match
from inroad_lite.api.schemas.errors import ApiError
from inroad_lite.api.schemas.profile import Profile
from inroad_lite.api.services.match_discovery import discovery_request
from inroad_lite.sourcing.api import dependencies
from tests.support.fake_boards import FakeBoards, lever_listing, lever_url
from tests.support.fake_olostep import FakeOlostep, search_body

PROFILE = Profile(
    roles=["Backend Engineer"],
    skills=["Python", "python", "Docker", "AWS", "Go", "Rust", "SQL", "Kafka"],
    location="Lahore, Pakistan",
    work_preference=["remote", "hybrid"],
    years_experience=4,
)
SEARCH_LINKS = [
    {"url": "https://jobs.lever.co/acme/a1", "title": "Acme - Backend Engineer"},
    {"url": "https://jobs.lever.co/usonly/u1", "title": "UsOnly - Backend Engineer"},
    {"url": "https://jobs.lever.co/acme/x9", "title": "Acme - Sales Lead"},
]
HOMEPAGE = (
    "# Acme\n\n[Pricing](/p) [Docs](/d)\n\n"
    "Acme builds developer tools that help small teams ship backend services faster.\n"
)


def olostep(payload: dict[str, object]) -> httpx.Response:
    if "url_to_scrape" in payload:
        return httpx.Response(
            200, json={"credits_consumed": 1, "result": {"markdown_content": HOMEPAGE}}
        )
    if "official website" in str(payload["query"]):
        return httpx.Response(200, json=search_body([{"url": "https://www.acme.dev/"}]))
    return httpx.Response(200, json=search_body(SEARCH_LINKS))


def boards() -> FakeBoards:
    acme = lever_listing("acme", [("a1", "Backend Engineer", "remote")])
    acme[0]["categories"] = {"location": "Remote - Worldwide", "allLocations": ["Worldwide"]}
    return FakeBoards(
        {
            lever_url("acme"): acme,
            lever_url("usonly"): lever_listing("usonly", [("u1", "Backend Engineer", "remote")]),
        }
    )


def run(monkeypatch, **options):  # type: ignore[no-untyped-def]
    fake = FakeOlostep(olostep)
    board = boards()
    monkeypatch.setattr(dependencies, "make_olostep_client", lambda *_a, **_k: fake.client())
    monkeypatch.setattr(dependencies, "make_board_fetcher", lambda: board)
    return asyncio.run(match.find_companies(PROFILE, **options))


def test_only_what_the_search_needs_crosses_to_sourcing():
    sent = discovery_request(PROFILE).model_dump()
    assert set(sent) == {
        "roles", "keywords", "locations", "remote", "onsite", "relocation",
        "relocation_places", "fresh",
    }  # fmt: skip
    assert sent["keywords"] == ["Python", "Docker", "AWS", "Go", "Rust", "SQL"]
    assert sent["locations"] == ["Lahore", "Pakistan"]
    assert (sent["remote"], sent["onsite"], sent["relocation"]) == (True, True, False)


def test_only_companies_that_fit_are_ranked_with_their_reasons_and_about(monkeypatch):
    report = run(monkeypatch, about=1)

    assert [company.name for company in report.companies] == ["Acme"]
    acme = report.companies[0]
    assert acme.best_role.title == "Backend Engineer"
    reasons = {part.name: part.detail for part in acme.best_role.reasons}
    assert reasons["Role"] == "Matches your target Backend Engineer"
    assert reasons["Skills"] == "Names Python, Docker"
    assert reasons["Location"].startswith("Remote, open to Pakistan")
    assert (acme.website, acme.about) == (
        "acme.dev",
        "Acme builds developer tools that help small teams ship backend services faster.",
    )
    # New York only, for someone in Pakistan: read, proven, then left out here.
    assert report.left_out["not open where you can work"] == 1
    assert report.left_out["not the role searched for"] == len(report.searches)


def test_relaxed_keeps_roles_whatever_their_location(monkeypatch):
    report = run(monkeypatch, relaxed=True, about=0)
    assert sorted(company.name for company in report.companies) == ["Acme", "UsOnly"]
    us_only = next(c for c in report.companies if c.name == "UsOnly")
    location = next(p.detail for p in us_only.best_role.reasons if p.name == "Location")
    assert location.endswith("(location not checked)")
    assert report.relaxed


def test_the_count_says_how_many_fit_even_when_fewer_are_shown(monkeypatch):
    monkeypatch.setattr("inroad_lite.api.services.match_discovery.MAX_COMPANIES", 1)
    report = run(monkeypatch, relaxed=True, about=0)
    assert (report.companies_fitting, len(report.companies)) == (2, 1)


def test_a_missing_key_is_a_clear_error_not_a_crash():
    with pytest.raises(ApiError) as caught:
        asyncio.run(match.find_companies(PROFILE))
    assert caught.value.code == "olostep_auth"
    assert "OLOSTEP_API_KEY" in caught.value.message
