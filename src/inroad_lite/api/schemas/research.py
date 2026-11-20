from __future__ import annotations

from pydantic import BaseModel

from inroad_lite.api.schemas.match import OlostepSpend, RoleResult


class ResearchFact(BaseModel):
    category: str
    text: str
    # The sentence on the page that says it, and which page.
    quote: str
    source: str


class OpenRole(BaseModel):
    title: str
    url: str
    locations: list[str]
    workplace: str | None


class ResearchReport(BaseModel):
    domain: str
    name: str
    summary: str | None
    facts: list[ResearchFact]
    pages_read: list[str]
    job_board: str | None
    # Why no roles are listed, when none are.
    board_note: str | None
    open_roles_total: int
    open_roles: list[OpenRole]
    # Only when a profile was given: the open roles that fit it, best first.
    roles_that_fit: list[RoleResult] | None
    left_out: dict[str, int]
    olostep: OlostepSpend
