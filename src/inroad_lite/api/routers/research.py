"""The entry point web calls to research one company."""

from __future__ import annotations

from pydantic import ValidationError

from inroad_lite.api.schemas.errors import ApiError
from inroad_lite.api.schemas.profile import Profile
from inroad_lite.api.schemas.research import ResearchReport
from inroad_lite.api.services import company_research
from inroad_lite.api.services.sourcing_client import SourcingFailed


async def research_company(
    domain: str,
    *,
    profile: Profile | None = None,
    relaxed: bool = False,
    pages: int = 4,
    fresh: bool = False,
) -> ResearchReport:
    try:
        return await company_research.research(
            domain, profile=profile, relaxed=relaxed, pages=pages, fresh=fresh
        )
    except ValidationError:
        raise ApiError("invalid_domain", f"{domain!r} is not a public company website") from None
    except SourcingFailed as exc:
        raise ApiError(exc.code, exc.message) from None
