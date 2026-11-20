"""Find companies for a profile. Stage A in sourcing (search, then prove an
open posting), Stage B here (does each posting fit this person, and how
well), then the best few get an "about" from their homepage."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass

from inroad_lite.api.schemas.match import (
    CompanyResult,
    MatchReport,
    OlostepSpend,
    RoleResult,
    ScorePart,
)
from inroad_lite.api.schemas.profile import Profile
from inroad_lite.api.services import match_fit, sourcing_client
from inroad_lite.api.services.match_score import MatchScore, band, score_company, score_role
from inroad_lite.sourcing.schemas.company_discovery import (
    CompanyOut,
    DiscoveryRequestIn,
    OlostepUsageOut,
    PostingOut,
)
from inroad_lite.sourcing.schemas.company_profile import CompanyProfileIn, CompanyProfileOut

MAX_COMPANIES = 10
# Sourcing's reject codes in plain words.
_LEFT_OUT_REASONS = {
    "irrelevant": "not the role searched for",
    "aggregator": "a job site listing other companies' roles",
    "not_a_board": "not a Greenhouse, Lever or Ashby link",
    "unidentified_employer": "employer not readable from the link",
    "board_unreadable": "job board could not be read",
    "closed": "posting already closed",
    "no_matching_posting": "no open posting for your roles",
    "proof_timeout": "job board too slow to answer",
}
_LEVEL_REASONS = frozenset({"staff-level role", "senior role", "junior role"})


@dataclass(frozen=True)
class _Ranked:
    company: CompanyOut
    score: int
    roles: list[tuple[MatchScore, PostingOut]]


def discovery_request(profile: Profile, *, fresh: bool = False) -> DiscoveryRequestIn:
    """Only what the search needs crosses: at most 4 roles, 6 skill terms,
    a city and country, and the work modes. Never years of experience or
    anything else from the profile."""
    preferences = set(profile.work_preference)
    return DiscoveryRequestIn(
        roles=_generic(profile.roles, limit=4),
        keywords=_generic(profile.skills, limit=6),
        locations=[part for part in (profile.city, profile.country) if part],
        remote="remote" in preferences,
        onsite=bool(preferences & {"onsite", "hybrid"}),
        relocation="relocation" in preferences,
        relocation_places=_generic(profile.relocation_places, limit=4),
        fresh=fresh,
    )


async def find_companies(
    profile: Profile, *, fresh: bool = False, relaxed: bool = False, about: int = 3
) -> MatchReport:
    found = await sourcing_client.discover(discovery_request(profile, fresh=fresh))
    ranked, unfit = rank(profile, found.companies, relaxed=relaxed)
    fitting = len(ranked)
    ranked = ranked[:MAX_COMPANIES]
    profiles = await asyncio.gather(
        *(
            sourcing_client.profile(
                CompanyProfileIn(
                    name=r.company.company_name,
                    posting_urls=[p.url for p in r.company.postings],
                    fresh=fresh,
                )
            )
            for r in ranked[: max(about, 0)]
        )
    )
    left_out = Counter({_LEFT_OUT_REASONS.get(k, k): v for k, v in found.rejected.items()})
    left_out.update(unfit)
    spend = [found.olostep, *(p.olostep for p in profiles)]
    return MatchReport(
        searches=found.queries,
        failed_searches=found.failed_queries,
        results_seen=found.hits_seen,
        boards_read=found.candidates_found,
        companies_fitting=fitting,
        companies=[
            _company(r, profiles[i] if i < len(profiles) else None) for i, r in enumerate(ranked)
        ],
        left_out=dict(left_out.most_common()),
        relaxed=relaxed,
        olostep=_spend(spend),
    )


def rank(
    profile: Profile, companies: list[CompanyOut], *, relaxed: bool = False
) -> tuple[list[_Ranked], Counter[str]]:
    """Stage B: each posting checked against the person, the ones that fit
    scored, each company ranked by its best role and how many fit."""
    ranked: list[_Ranked] = []
    unfit: Counter[str] = Counter()
    for company in companies:
        verdicts = [(p, match_fit.fit(profile, p, relaxed=relaxed)) for p in company.postings]
        fitting = [(p, v) for p, v in verdicts if v.ok]
        if not fitting:
            # A company counts once, by its first posting's reason.
            unfit[unfit_words(verdicts[0][1].reason)] += 1
            continue
        roles = sorted(
            ((score_posting(profile, p, v.reason), p) for p, v in fitting),
            key=lambda pair: -pair[0].score,
        )
        ranked.append(_Ranked(company, score_company(roles[0][0], len(roles)), roles))
    ranked.sort(key=lambda r: (-r.score, r.company.company_name.lower()))
    return ranked, unfit


def score_posting(profile: Profile, posting: PostingOut, location: str) -> MatchScore:
    return score_role(
        targets=profile.roles,
        skills=profile.skills,
        years=profile.years_experience,
        title=posting.title,
        text=f"{posting.title}\n{posting.description or ''}",
        posted_at=posting.posted_at,
        location=location,
        described=posting.description is not None,
    )


def unfit_words(reason: str) -> str:
    if reason.startswith("location"):
        return "not open where you can work"
    if reason in _LEVEL_REASONS:
        return "wrong level for your experience"
    return "a different kind of role"


def _company(ranked: _Ranked, profile: CompanyProfileOut | None) -> CompanyResult:
    (best, best_posting), *others = ranked.roles
    company = ranked.company
    return CompanyResult(
        name=company.company_name,
        job_board=f"{company.ats_provider}: {company.ats_token}",
        score=ranked.score,
        band=band(ranked.score),
        website=profile.domain if profile else None,
        about=profile.summary if profile else None,
        best_role=role_result(best, best_posting),
        other_roles=[role_result(score, posting) for score, posting in others],
    )


def role_result(score: MatchScore, posting: PostingOut) -> RoleResult:
    return RoleResult(
        title=posting.title,
        url=posting.url,
        score=score.score,
        band=score.band,
        reasons=[ScorePart(name=part.name, detail=part.detail) for part in score.parts],
    )


def _spend(usages: list[OlostepUsageOut]) -> OlostepSpend:
    return OlostepSpend(
        calls=sum(u.calls for u in usages),
        credits=sum(u.credits for u in usages),
        answered_from_cache=sum(u.cache_hits for u in usages),
    )


def _generic(values: list[str], *, limit: int) -> list[str]:
    """Trimmed, blanks and repeats dropped, first spelling kept, capped."""
    kept: list[str] = []
    for value in values:
        text = " ".join(value.split())[:80]
        if text and text.lower() not in {k.lower() for k in kept}:
            kept.append(text)
    return kept[:limit]
