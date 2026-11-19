from __future__ import annotations

import asyncio

from inroad_lite.sourcing.domain.company_discovery import (
    Candidate,
    DiscoveryPolicy,
    PostingLead,
    ProvenCompany,
    RejectReason,
)
from inroad_lite.sourcing.services.candidate_proof import CandidateProver
from tests.support.fake_boards import (
    FakeBoards,
    greenhouse_listing,
    greenhouse_url,
    lever_listing,
    lever_url,
)

ROLES = ("Backend Engineer",)


def candidate(provider: str, token: str, *posting_ids: str | None) -> Candidate:
    return Candidate(
        company_name=token.capitalize(),
        ats_provider=provider,
        ats_token=token,
        ats_region=None,
        leads=[PostingLead(p, "Backend Engineer", f"https://x/{p}") for p in posting_ids],
    )


def prove(boards: FakeBoards, *candidates: Candidate, policy: DiscoveryPolicy | None = None):  # type: ignore[no-untyped-def]
    prover = CandidateProver(boards, policy or DiscoveryPolicy())
    return asyncio.run(_all(prover, candidates))


async def _all(prover: CandidateProver, candidates):  # type: ignore[no-untyped-def]
    return [await prover.prove(c, ROLES) for c in candidates]


def test_a_found_posting_is_proven_with_the_boards_own_company_name_and_description():
    boards = FakeBoards(
        {
            greenhouse_url("acme"): greenhouse_listing(
                "acme", [(11, "Backend Engineer", "Remote")], "Acme Robotics"
            ),
            greenhouse_url("acme", "11"): {"content": "&lt;p&gt;Python and Go&lt;/p&gt;"},
        }
    )
    (proven,) = prove(boards, candidate("greenhouse", "acme", "11"))
    assert isinstance(proven, ProvenCompany)
    assert proven.company_name == "Acme Robotics"
    (posting,) = proven.postings
    assert (posting.title, posting.workplace, posting.description) == (
        "Backend Engineer",
        "remote",
        "Python and Go",
    )


def test_a_posting_missing_from_a_whole_listing_is_closed_from_a_partial_one_unknown():
    whole = greenhouse_listing("acme", [(12, "Other", "x")], "Acme")
    partial = greenhouse_listing("beta", [(12, "Other", "x")], "Beta", total=90)
    boards = FakeBoards({greenhouse_url("acme"): whole, greenhouse_url("beta"): partial})
    closed, unknown = prove(
        boards, candidate("greenhouse", "acme", "11"), candidate("greenhouse", "beta", "11")
    )
    assert closed is RejectReason.CLOSED
    assert unknown is RejectReason.BOARD_UNREADABLE


def test_a_board_page_hit_finds_postings_for_the_roles_or_none():
    jobs = [("a1", "Senior Backend Engineer", "remote"), ("a2", "Recruiter", "onsite")]
    boards = FakeBoards(
        {
            lever_url("acme"): lever_listing("acme", jobs),
            lever_url("beta"): lever_listing("beta", [("b", "Recruiter", "remote")]),
        }
    )
    found, none = prove(boards, candidate("lever", "acme", None), candidate("lever", "beta", None))
    assert isinstance(found, ProvenCompany)
    assert [p.title for p in found.postings] == ["Senior Backend Engineer"]
    assert none is RejectReason.NO_MATCHING_POSTING


def test_an_unreadable_board_is_left_out():
    (result,) = prove(FakeBoards({}), candidate("lever", "gone", "x1"))
    assert result is RejectReason.BOARD_UNREADABLE


def test_each_board_is_read_once_for_every_candidate_on_it():
    boards = FakeBoards(
        {lever_url("acme"): lever_listing("acme", [("a1", "Backend Engineer", "remote")])}
    )
    prove(boards, candidate("lever", "acme", "a1"), candidate("lever", "acme", None))
    assert boards.requests == [lever_url("acme")]


def test_a_board_too_slow_to_answer_is_left_out():
    boards = FakeBoards(
        {lever_url("acme"): lever_listing("acme", [("a1", "Backend Engineer", "remote")])},
        delay=0.5,
    )
    (result,) = prove(
        boards, candidate("lever", "acme", "a1"), policy=DiscoveryPolicy(proof_timeout_seconds=0.05)
    )
    assert result is RejectReason.PROOF_TIMEOUT
