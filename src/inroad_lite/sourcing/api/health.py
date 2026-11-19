from __future__ import annotations

from inroad_lite.core.settings import load_settings
from inroad_lite.sourcing.api import dependencies
from inroad_lite.sourcing.domain.olostep import OlostepError
from inroad_lite.sourcing.schemas.company_discovery import OlostepCheck

_PROBE_QUERY = "software engineer jobs"


async def check_olostep() -> OlostepCheck:
    """One real, uncached search: proves the key and the network."""
    settings = load_settings()
    try:
        async with dependencies.make_olostep_client(settings, fresh=True) as client:
            hits = await client.search(_PROBE_QUERY)
    except OlostepError as exc:
        return OlostepCheck(ok=False, error=str(exc))
    return OlostepCheck(ok=True, results=len(hits), credits=client.usage.credits)
