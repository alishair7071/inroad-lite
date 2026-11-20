"""Sourcing's public contract for company discovery: the only sourcing types
inroad-lite's api sees. Plain data in and out, so it could travel as JSON
if sourcing ran as a separate service."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class DiscoveryRequestIn(BaseModel):
    """No user data: roles, a few skill terms, a place and work modes."""

    model_config = ConfigDict(extra="forbid")

    roles: list[Short] = Field(min_length=1, max_length=4)
    keywords: list[Short] = Field(default_factory=list, max_length=6)
    locations: list[Short] = Field(default_factory=list, max_length=2)
    remote: bool = False
    onsite: bool = False
    relocation: bool = False
    relocation_places: list[Short] = Field(default_factory=list, max_length=4)
    # True asks Olostep again instead of answering from the cache.
    fresh: bool = False


class PostingOut(BaseModel):
    """An open posting, as read from the company's own job board."""

    posting_id: str
    title: str
    url: str
    locations: list[str]
    # remote | hybrid | onsite, or None when the board does not say.
    workplace: str | None
    # ISO 3166-1 alpha-2, when the board states one.
    country: str | None
    description: str | None
    posted_at: str | None
    # offered | not_offered | not_stated
    visa_sponsorship: str
    relocation_support: str


class CompanyOut(BaseModel):
    company_name: str
    ats_provider: str
    ats_token: str
    postings: list[PostingOut]


class OlostepUsageOut(BaseModel):
    calls: int
    credits: int
    cache_hits: int
    failures: int


class DiscoveryResponse(BaseModel):
    queries: list[str]
    failed_queries: list[str]
    hits_seen: int
    # Companies whose boards were read; `companies` are the ones proven.
    candidates_found: int
    companies: list[CompanyOut]
    # Reason code -> how many hits were rejected for it.
    rejected: dict[str, int]
    olostep: OlostepUsageOut


class OlostepCheck(BaseModel):
    ok: bool
    results: int = 0
    credits: int = 0
    error: str | None = None


class SourcingError(Exception):
    """A failed request, with a stable code and a message safe to show."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
