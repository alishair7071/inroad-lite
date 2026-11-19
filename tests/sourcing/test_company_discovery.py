from __future__ import annotations

import asyncio

import httpx

from inroad_lite.sourcing.domain.company_discovery import DiscoveryRequest
from inroad_lite.sourcing.services.candidate_proof import CandidateProver
from inroad_lite.sourcing.services.company_discovery import discover_companies
from tests.support.fake_boards import (
    FakeBoards,
    ashby_listing,
    ashby_url,
    lever_listing,
    lever_url,
)
from tests.support.fake_olostep import FakeOlostep, search_body

REQUEST = DiscoveryRequest(roles=("Backend Engineer", "DevOps Engineer"), remote=True)


def links_for(payload: dict[str, object]) -> list[dict[str, str]]:
    if str(payload["query"]).startswith('"Backend Engineer"'):
        return [
            {"url": "https://jobs.lever.co/acme/1", "title": "Acme - Backend Engineer"},
            {"url": "https://www.indeed.com/viewjob?jk=1", "title": "Backend Engineer"},
        ]
    return [
        {"url": "https://jobs.lever.co/acme/2", "title": "Acme - DevOps Engineer"},
        {"url": "https://jobs.ashbyhq.com/beta/9", "title": "DevOps Engineer at Beta"},
        {"url": "https://jobs.lever.co/gamma/7", "title": "Gamma - DevOps Engineer"},
    ]


BOARDS = {
    lever_url("acme"): lever_listing(
        "acme", [("1", "Backend Engineer", "remote"), ("2", "DevOps Engineer", "remote")]
    ),
    ashby_url("beta"): ashby_listing("beta", [("9", "DevOps Engineer")]),
    # gamma's board no longer lists posting 7
    lever_url("gamma"): lever_listing("gamma", [("8", "Designer", "onsite")]),
}


def run(respond):  # type: ignore[no-untyped-def]
    fake = FakeOlostep(respond)
    boards = FakeBoards(BOARDS)

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            return await discover_companies(REQUEST, client, CandidateProver(boards))

    return asyncio.run(go()), boards


def test_hits_are_merged_by_board_and_only_open_postings_are_kept():
    outcome, boards = run(lambda p: httpx.Response(200, json=search_body(links_for(p))))
    assert len(outcome.queries) == 2
    assert outcome.hits_seen == 5
    assert outcome.candidates_found == 3
    assert [(c.company_name, len(c.postings)) for c in outcome.companies] == [
        ("Acme", 2),
        ("Beta", 1),
    ]
    assert outcome.rejected == {"not_a_board": 1, "closed": 1}
    assert len(boards.requests) == 3


def test_a_search_that_fails_does_not_cost_the_others():
    def respond(payload: dict[str, object]) -> httpx.Response:
        if str(payload["query"]).startswith('"Backend Engineer"'):
            raise httpx.ReadTimeout("slow")
        return httpx.Response(200, json=search_body(links_for(payload)))

    outcome, _ = run(respond)
    assert [c.company_name for c in outcome.companies] == ["Acme", "Beta"]
    assert len(outcome.failed_queries) == 1
