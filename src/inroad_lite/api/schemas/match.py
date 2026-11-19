from __future__ import annotations

from pydantic import BaseModel


class ScorePart(BaseModel):
    name: str
    detail: str


class RoleResult(BaseModel):
    title: str
    url: str
    score: int
    band: str
    # Why it scored what it did, one line per part (role, skills, level...).
    reasons: list[ScorePart]


class CompanyResult(BaseModel):
    name: str
    job_board: str
    score: int
    band: str
    website: str | None = None
    about: str | None = None
    best_role: RoleResult
    other_roles: list[RoleResult]


class OlostepSpend(BaseModel):
    calls: int
    credits: int
    answered_from_cache: int


class MatchReport(BaseModel):
    searches: list[str]
    failed_searches: list[str]
    results_seen: int
    boards_read: int
    # Best first.
    companies: list[CompanyResult]
    # Plain-words reason -> how many were left out for it.
    left_out: dict[str, int]
    # True when location and level were not checked (--relaxed).
    relaxed: bool
    olostep: OlostepSpend
