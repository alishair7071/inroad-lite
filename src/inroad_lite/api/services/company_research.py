"""Research one company: sourcing reads the site and its job board; api adds,
when a profile is given, which of the company's open roles fit the person,
by the same rules and score as matching (Stage B). Mirrors inroad-api, which
maps sourcing's research into the company record with its fitting roles."""

from __future__ import annotations

from collections import Counter

from inroad_lite.api.schemas.match import OlostepSpend, RoleResult
from inroad_lite.api.schemas.profile import Profile
from inroad_lite.api.schemas.research import OpenRole, ResearchFact, ResearchReport
from inroad_lite.api.services import match_fit, sourcing_client
from inroad_lite.api.services.match_discovery import role_result, score_posting, unfit_words
from inroad_lite.sourcing.schemas.company_discovery import PostingOut
from inroad_lite.sourcing.schemas.company_research import CompanyResearchIn

OPEN_ROLES_SHOWN = 15
FITTING_ROLES_SHOWN = 10


async def research(
    domain: str,
    *,
    profile: Profile | None = None,
    relaxed: bool = False,
    pages: int = 4,
    fresh: bool = False,
) -> ResearchReport:
    found = await sourcing_client.research(
        CompanyResearchIn(domain=domain, max_pages=pages, fresh=fresh)
    )
    fitting, left_out = (
        _fitting(profile, found.openings, relaxed=relaxed) if profile else (None, Counter())
    )
    return ResearchReport(
        domain=found.domain,
        name=found.name,
        summary=found.summary,
        facts=[
            ResearchFact(category=f.category, text=f.text, quote=f.quote, source=f.source_url)
            for f in found.facts
        ],
        pages_read=[page.url for page in found.pages_read],
        job_board=found.job_board,
        board_note=found.board_note,
        open_roles_total=len(found.openings),
        open_roles=[
            OpenRole(title=p.title, url=p.url, locations=p.locations, workplace=p.workplace)
            for p in found.openings[:OPEN_ROLES_SHOWN]
        ],
        roles_that_fit=fitting,
        left_out=dict(left_out.most_common()),
        olostep=OlostepSpend(
            calls=found.olostep.calls,
            credits=found.olostep.credits,
            answered_from_cache=found.olostep.cache_hits,
        ),
    )


def _fitting(
    profile: Profile, openings: list[PostingOut], *, relaxed: bool
) -> tuple[list[RoleResult], Counter[str]]:
    scored = []
    left_out: Counter[str] = Counter()
    for posting in openings:
        verdict = match_fit.fit(profile, posting, relaxed=relaxed)
        if verdict.ok:
            scored.append((score_posting(profile, posting, verdict.reason), posting))
        else:
            left_out[unfit_words(verdict.reason)] += 1
    scored.sort(key=lambda pair: -pair[0].score)
    return [role_result(s, p) for s, p in scored[:FITTING_ROLES_SHOWN]], left_out
