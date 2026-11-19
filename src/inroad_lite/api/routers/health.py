from __future__ import annotations

from inroad_lite.api.schemas.health import OlostepHealth
from inroad_lite.api.services import sourcing_client


async def check_olostep() -> OlostepHealth:
    found = await sourcing_client.check_olostep()
    return OlostepHealth(
        ok=found.ok, results=found.results, credits=found.credits, error=found.error
    )
