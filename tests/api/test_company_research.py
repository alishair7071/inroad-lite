from __future__ import annotations

import asyncio

import httpx
import pytest

from inroad_lite.api.routers.research import research_company
from inroad_lite.api.schemas.errors import ApiError
from inroad_lite.api.schemas.profile import Profile
from inroad_lite.sourcing.api import dependencies
from tests.support.fake_boards import FakeBoards, lever_listing, lever_url
from tests.support.fake_olostep import FakeOlostep

PROFILE = Profile(
    roles=["Backend Engineer"],
    skills=["Python"],
    location="Lahore, Pakistan",
    work_preference=["remote"],
    years_experience=2,
)
HOME = (
    "# Acme\n\nAcme builds developer tools that help small teams ship backend services.\n\n"
    "[Careers](https://jobs.lever.co/acme)\n"
)


def run(monkeypatch, domain: str = "acme.com", **options):  # type: ignore[no-untyped-def]
    def respond(payload: dict[str, object]) -> httpx.Response:
        body = {"credits_consumed": 1, "result": {"markdown_content": HOME}}
        return httpx.Response(200, json=body)

    jobs = lever_listing(
        "acme", [("a1", "Backend Engineer", "remote"), ("a2", "Recruiter", "remote")]
    )
    for job in jobs:  # both open to Pakistan, so the role rule decides
        job["categories"] = {"allLocations": ["Remote - Worldwide"]}
    boards = FakeBoards({lever_url("acme"): jobs})
    fake = FakeOlostep(respond)
    monkeypatch.setattr(dependencies, "make_olostep_client", lambda *_a, **_k: fake.client())
    monkeypatch.setattr(dependencies, "make_board_fetcher", lambda: boards)
    return asyncio.run(research_company(domain, **options))


def test_with_a_profile_the_roles_that_fit_are_scored(monkeypatch):
    report = run(monkeypatch, profile=PROFILE)
    assert report.open_roles_total == 2
    assert [role.title for role in report.roles_that_fit or []] == ["Backend Engineer"]
    assert report.left_out == {"a different kind of role": 1}
    assert report.olostep.credits == 1


def test_without_a_profile_there_is_no_fit_section(monkeypatch):
    report = run(monkeypatch)
    assert report.roles_that_fit is None
    assert (
        report.summary == "Acme builds developer tools that help small teams ship backend services."
    )


def test_a_website_that_is_not_public_is_refused_before_anything_runs(monkeypatch):
    with pytest.raises(ApiError) as caught:
        run(monkeypatch, domain="localhost:8000")
    assert caught.value.code == "invalid_domain"
