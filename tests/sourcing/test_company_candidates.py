from __future__ import annotations

from inroad_lite.sourcing.discovery.company_candidates import (
    ATS_QUERY,
    build_queries,
    candidate_from_hit,
)
from inroad_lite.sourcing.domain.company_discovery import Candidate, DiscoveryRequest, RejectReason
from inroad_lite.sourcing.domain.olostep import SearchHit

ROLES = ("Backend Engineer",)


def request(**overrides: object) -> DiscoveryRequest:
    values: dict[str, object] = {
        "roles": ("Backend Engineer", "DevOps Engineer"),
        "keywords": ("Python", "Docker", "AWS"),
        "locations": ("Lahore", "Pakistan"),
        "remote": True,
        "relocation": True,
    }
    values.update(overrides)
    return DiscoveryRequest(**values)  # type: ignore[arg-type]


def candidate(url: str, title: str | None = None) -> Candidate | RejectReason:
    return candidate_from_hit(SearchHit(url=url, title=title), roles=ROLES)


# Queries


def test_each_role_gets_the_next_work_mode_first():
    queries = build_queries(request(), limit=2)
    assert queries[0].startswith('"Backend Engineer" Python remote (worldwide OR anywhere')
    assert "OR Pakistan)" in queries[0]
    assert queries[1].startswith('"DevOps Engineer" Docker ("visa sponsorship" OR relocation)')
    assert all(query.endswith(ATS_QUERY) for query in queries)


def test_the_other_modes_follow_up_to_the_limit():
    queries = build_queries(request(), limit=4)
    assert len(queries) == 4
    assert "relocation" in queries[2] and queries[2].startswith('"Backend Engineer"')
    assert "remote" in queries[3] and queries[3].startswith('"DevOps Engineer"')


def test_onsite_names_the_place_and_carries_no_skill():
    (query,) = build_queries(
        request(roles=("Backend Engineer",), remote=False, relocation=False, onsite=True), limit=4
    )
    assert query == f'"Backend Engineer" (Lahore OR Pakistan) {ATS_QUERY}'


def test_relocation_asks_for_the_chosen_places():
    (query,) = build_queries(
        request(roles=("Backend Engineer",), remote=False,
                relocation_places=("Europe", "Canada")),
        limit=4,
    )  # fmt: skip
    assert '("visa sponsorship" OR relocation) (Europe OR Canada)' in query


def test_no_mode_and_no_place_carries_two_skills():
    (query,) = build_queries(
        request(roles=("Backend Engineer",), locations=(), remote=False, relocation=False),
        limit=4,
    )
    assert query == f'"Backend Engineer" Python Docker {ATS_QUERY}'


# Candidates from hits


def test_a_greenhouse_posting_names_its_company_and_posting():
    found = candidate(
        "https://job-boards.greenhouse.io/acmeinc/jobs/4567",
        "Job Application for Backend Engineer at Acme Inc",
    )
    assert isinstance(found, Candidate)
    assert (found.company_name, found.ats_provider, found.ats_token) == (
        "Acme Inc",
        "greenhouse",
        "acmeinc",
    )
    assert (found.leads[0].posting_id, found.leads[0].role_title) == ("4567", "Backend Engineer")


def test_a_lever_title_is_read_whichever_way_round_it_is():
    company_first = candidate("https://jobs.lever.co/acme/abc", "Acme - Senior Backend Engineer")
    role_first = candidate("https://jobs.lever.co/acme/abc", "Senior Backend Engineer - Acme")
    assert isinstance(company_first, Candidate) and isinstance(role_first, Candidate)
    assert company_first.company_name == role_first.company_name == "Acme"
    assert company_first.leads[0].role_title == role_first.leads[0].role_title


def test_an_ashby_board_page_is_kept_to_be_searched_later():
    found = candidate("https://jobs.ashbyhq.com/acme", "Acme Jobs")
    assert isinstance(found, Candidate)
    assert (found.leads[0].posting_id, found.leads[0].role_title) == (None, None)


def test_without_a_title_the_company_comes_from_the_board_name():
    found = candidate("https://jobs.lever.co/blue-river/abc")
    assert isinstance(found, Candidate) and found.company_name == "Blue River"


def test_hits_that_are_not_usable_are_rejected_with_a_reason():
    assert candidate("https://jobs.lever.co/acme/abc", "Acme - Sales Manager") is (
        RejectReason.IRRELEVANT
    )
    assert candidate("https://jobs.lever.co/jobgether/abc", "x") is RejectReason.AGGREGATOR
    assert candidate("https://www.linkedin.com/jobs/view/1", "x") is RejectReason.NOT_A_BOARD
    assert candidate("https://jobs.lever.co/", "x") is RejectReason.UNIDENTIFIED_EMPLOYER
