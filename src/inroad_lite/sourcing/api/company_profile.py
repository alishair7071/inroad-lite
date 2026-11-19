"""Sourcing's entry point for a company's "about"."""

from __future__ import annotations

from inroad_lite.core.settings import load_settings
from inroad_lite.sourcing.api import dependencies
from inroad_lite.sourcing.domain.olostep import OlostepAuthError
from inroad_lite.sourcing.schemas.company_discovery import OlostepUsageOut, SourcingError
from inroad_lite.sourcing.schemas.company_profile import CompanyProfileIn, CompanyProfileOut
from inroad_lite.sourcing.services.company_profile import company_profile


async def profile(body: CompanyProfileIn) -> CompanyProfileOut:
    settings = load_settings()
    try:
        async with dependencies.make_olostep_client(settings, fresh=body.fresh) as client:
            found = await company_profile(body.name, body.posting_urls, client)
    except OlostepAuthError as exc:
        raise SourcingError("olostep_auth", str(exc)) from None
    return CompanyProfileOut(
        name=found.name,
        domain=found.domain,
        summary=found.summary,
        olostep=OlostepUsageOut(**vars(client.usage)),
    )
