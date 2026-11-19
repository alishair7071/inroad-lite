from __future__ import annotations

from inroad_lite.core.cache import FileCache, NoCache
from inroad_lite.core.settings import Settings
from inroad_lite.sourcing.net.fetcher import BoardFetcher
from inroad_lite.sourcing.net.olostep import OlostepClient

SEARCH_CACHE_SECONDS = 6 * 3600


def make_olostep_client(settings: Settings, *, fresh: bool) -> OlostepClient:
    cache = (
        NoCache()
        if fresh
        else FileCache(settings.cache_dir / "olostep", ttl_seconds=SEARCH_CACHE_SECONDS)
    )
    return OlostepClient(
        api_key=settings.olostep_api_key,
        base_url=settings.olostep_base_url,
        timeout_seconds=settings.olostep_timeout_seconds,
        cache=cache,
    )


def make_board_fetcher() -> BoardFetcher:
    return BoardFetcher()
