"""Sourcing's public contract for researching one company. In Inroad this is
POST /v1/company-research then GET .../dossier; here a function with the
same idea: a domain in, what the site says and its open roles out."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from inroad_lite.sourcing.discovery.company_sites import research_target
from inroad_lite.sourcing.schemas.company_discovery import OlostepUsageOut, PostingOut


class CompanyResearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(max_length=253)
    # Pages read besides the homepage: one Olostep scrape each.
    max_pages: int = Field(default=4, ge=0, le=8)
    fresh: bool = False

    @field_validator("domain")
    @classmethod
    def _public_domain(cls, value: str) -> str:
        domain = research_target(value)
        if domain is None:
            raise ValueError("not a public company website")
        return domain


class FactOut(BaseModel):
    category: str
    text: str
    # The sentence on the page that states it.
    quote: str
    source_url: str


class PageOut(BaseModel):
    url: str
    kind: str


class CompanyResearchOut(BaseModel):
    domain: str
    name: str
    summary: str | None
    pages_read: list[PageOut]
    facts: list[FactOut]
    # "greenhouse: acme", or None when the site links no board inroad-lite reads.
    job_board: str | None
    board_note: str | None
    openings: list[PostingOut]
    olostep: OlostepUsageOut
