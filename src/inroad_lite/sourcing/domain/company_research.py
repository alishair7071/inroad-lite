"""Company research's types. Pure. Mirrors the shape of inroad-sourcing's
research run: the site's pages, what they say (with evidence), and the
company's open roles."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from inroad_lite.sourcing.domain.jobs import BoardRef, Job


class PageKind(StrEnum):
    HOME = "home"
    ABOUT = "about"
    CAREERS = "careers"
    PRODUCT = "product"
    TEAM = "team"
    CUSTOMERS = "customers"
    NEWS = "news"


@dataclass(frozen=True)
class SitePage:
    url: str
    kind: PageKind


@dataclass(frozen=True)
class Fact:
    """One thing the site says, with the sentence it says it in."""

    category: str
    text: str
    quote: str
    source_url: str


@dataclass(frozen=True)
class ResearchPolicy:
    # Pages read besides the homepage; each is one Olostep scrape.
    max_pages: int = 4


DEFAULT_RESEARCH_POLICY = ResearchPolicy()


@dataclass
class CompanyResearch:
    domain: str
    name: str
    summary: str | None
    pages_read: list[SitePage] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    job_board: BoardRef | None = None
    # How the board was found, or why there are no openings.
    board_note: str | None = None
    openings: list[Job] = field(default_factory=list)
