from __future__ import annotations

from dataclasses import dataclass


class OlostepError(Exception):
    """A short reason only: never the key, never a response body."""


class OlostepAuthError(OlostepError):
    pass


class OlostepUnavailable(OlostepError):
    pass


class OlostepRejected(OlostepError):
    pass


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str | None = None
    # The result's snippet. Data only: never fetched, never trusted.
    description: str | None = None


@dataclass
class OlostepUsage:
    """What one run asked of Olostep."""

    calls: int = 0
    credits: int = 0
    cache_hits: int = 0
    failures: int = 0
