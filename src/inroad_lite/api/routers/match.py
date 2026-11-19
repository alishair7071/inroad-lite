"""The entry point web calls to find companies. In Inroad a router is HTTP
only; here it is the same thin layer: take the input, call the service,
turn failures into an ApiError."""

from __future__ import annotations

from inroad_lite.api.schemas.errors import ApiError
from inroad_lite.api.schemas.match import MatchReport
from inroad_lite.api.schemas.profile import Profile
from inroad_lite.api.services import match_discovery
from inroad_lite.api.services.sourcing_client import SourcingFailed


async def find_companies(
    profile: Profile, *, fresh: bool = False, relaxed: bool = False, about: int = 3
) -> MatchReport:
    try:
        return await match_discovery.find_companies(
            profile, fresh=fresh, relaxed=relaxed, about=about
        )
    except SourcingFailed as exc:
        raise ApiError(exc.code, exc.message) from None
