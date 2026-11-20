"""The only way api reaches sourcing. Here it is a function call, so this
file is the one place to change to run sourcing as a separate service."""

from __future__ import annotations

from inroad_lite.sourcing.api import company_discovery, company_profile, company_research, health
from inroad_lite.sourcing.schemas.company_discovery import (
    DiscoveryRequestIn,
    DiscoveryResponse,
    OlostepCheck,
    SourcingError,
)
from inroad_lite.sourcing.schemas.company_profile import CompanyProfileIn, CompanyProfileOut
from inroad_lite.sourcing.schemas.company_research import CompanyResearchIn, CompanyResearchOut


class SourcingFailed(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def discover(request: DiscoveryRequestIn) -> DiscoveryResponse:
    try:
        return await company_discovery.discover(request)
    except SourcingError as exc:
        raise SourcingFailed(exc.code, exc.message) from None


async def profile(request: CompanyProfileIn) -> CompanyProfileOut:
    try:
        return await company_profile.profile(request)
    except SourcingError as exc:
        raise SourcingFailed(exc.code, exc.message) from None


async def research(request: CompanyResearchIn) -> CompanyResearchOut:
    try:
        return await company_research.research(request)
    except SourcingError as exc:
        raise SourcingFailed(exc.code, exc.message) from None


async def check_olostep() -> OlostepCheck:
    return await health.check_olostep()
