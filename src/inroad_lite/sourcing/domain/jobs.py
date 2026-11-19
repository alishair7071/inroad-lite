"""A job board and the postings read from it, the same shape whichever board
it came from. Pure types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardRef:
    provider: str  # greenhouse | lever | ashby
    token: str
    # Lever runs a separate EU deployment.
    region: str | None = None


@dataclass(frozen=True)
class Job:
    external_id: str
    title: str
    url: str
    locations: tuple[str, ...] = ()
    # remote | hybrid | onsite, or None when the board does not say.
    workplace: str | None = None
    # An ISO code once proven; the board's own spelling before.
    country: str | None = None
    description: str | None = None
    posted_at: str | None = None
    # offered | not_offered | not_stated, read from the posting's own text.
    visa_sponsorship: str = "not_stated"
    relocation_support: str = "not_stated"


@dataclass(frozen=True)
class BoardScan:
    jobs: tuple[Job, ...]
    # True only when the whole listing is known to have arrived: only then
    # does a missing posting prove it closed.
    complete: bool
    # Greenhouse names the company; Lever and Ashby do not.
    company_name: str | None = None
