"""Company discovery's types. Pure: no network, no Pydantic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from inroad_lite.sourcing.domain.jobs import Job


@dataclass(frozen=True)
class DiscoveryRequest:
    """Everything sourcing is told about the person: never a profile, a
    name, years of experience or saved companies."""

    roles: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    # A city, then optionally its country.
    locations: tuple[str, ...] = ()
    remote: bool = False
    onsite: bool = False
    relocation: bool = False
    # Region names a relocation search asks for ("Canada", "Europe").
    relocation_places: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryPolicy:
    # Each Olostep search is billable, so a run is capped.
    max_query_searches: int = 4
    max_hits_per_query: int = 10
    # Boards read per run; every one is a request to a public job board.
    max_candidates_to_prove: int = 25
    # A board that has not answered by then is left out, not waited for.
    proof_timeout_seconds: float = 25.0
    max_postings_per_company: int = 3


DEFAULT_DISCOVERY_POLICY = DiscoveryPolicy()


class RejectReason(StrEnum):
    # From the search hit
    NOT_A_BOARD = "not_a_board"
    AGGREGATOR = "aggregator"
    IRRELEVANT = "irrelevant"
    UNIDENTIFIED_EMPLOYER = "unidentified_employer"
    # From reading the board
    BOARD_UNREADABLE = "board_unreadable"
    CLOSED = "closed"
    NO_MATCHING_POSTING = "no_matching_posting"
    PROOF_TIMEOUT = "proof_timeout"


@dataclass(frozen=True)
class PostingLead:
    """One search hit: a posting, or the board's home page when posting_id
    is None."""

    posting_id: str | None
    role_title: str | None
    url: str


@dataclass
class Candidate:
    """One company's job board and the hits that point at it."""

    company_name: str
    ats_provider: str
    ats_token: str
    ats_region: str | None
    leads: list[PostingLead] = field(default_factory=list)


@dataclass(frozen=True)
class ProvenCompany:
    """A candidate whose board was read and holds at least one open posting
    for the searched roles."""

    company_name: str
    ats_provider: str
    ats_token: str
    postings: tuple[Job, ...]
