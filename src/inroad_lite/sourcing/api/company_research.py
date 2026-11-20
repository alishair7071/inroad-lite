"""Sourcing's entry point for researching one company."""

from __future__ import annotations

from inroad_lite.core.settings import load_settings
from inroad_lite.sourcing.api import dependencies
from inroad_lite.sourcing.api.company_discovery import posting_out
from inroad_lite.sourcing.domain.company_research import ResearchPolicy
from inroad_lite.sourcing.domain.olostep import OlostepAuthError
from inroad_lite.sourcing.schemas.company_discovery import OlostepUsageOut, SourcingError
from inroad_lite.sourcing.schemas.company_research import (
    CompanyResearchIn,
    CompanyResearchOut,
    FactOut,
    PageOut,
)
from inroad_lite.sourcing.services.company_research import SiteUnreadable, research_company


async def research(body: CompanyResearchIn) -> CompanyResearchOut:
    settings = load_settings()
    try:
        async with (
            dependencies.make_olostep_client(settings, fresh=body.fresh) as client,
            dependencies.make_board_fetcher() as fetcher,
        ):
            found = await research_company(
                body.domain, client, fetcher, ResearchPolicy(max_pages=body.max_pages)
            )
    except OlostepAuthError as exc:
        raise SourcingError("olostep_auth", str(exc)) from None
    except SiteUnreadable as exc:
        raise SourcingError("site_unreadable", f"Could not read {body.domain}: {exc}") from None
    board = found.job_board
    return CompanyResearchOut(
        domain=found.domain,
        name=found.name,
        summary=found.summary,
        pages_read=[PageOut(url=page.url, kind=page.kind.value) for page in found.pages_read],
        facts=[
            FactOut(category=f.category, text=f.text, quote=f.quote, source_url=f.source_url)
            for f in found.facts
        ],
        job_board=f"{board.provider}: {board.token}" if board else None,
        board_note=found.board_note,
        openings=[posting_out(job) for job in found.openings],
        olostep=OlostepUsageOut(**vars(client.usage)),
    )
