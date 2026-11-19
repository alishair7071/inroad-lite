"""What every board reader provides. Readers build URLs and turn payloads
into Jobs; they never fetch (only sourcing's net layer does, a test holds
it). Mirrors inroad-sourcing's app/ats/base.py."""

from __future__ import annotations

from typing import Any, Protocol

from inroad_lite.sourcing.domain.jobs import BoardRef, BoardScan, Job


class MalformedListing(Exception):
    pass


class BoardAdapter(Protocol):
    provider: str

    def hosts(self, ref: BoardRef) -> frozenset[str]: ...

    def listing_url(self, ref: BoardRef) -> str: ...

    def parse_listing(self, payload: Any) -> BoardScan: ...

    def detail_url(self, ref: BoardRef, job: Job) -> str | None:
        """None when the listing already carries the description."""
        ...

    def parse_detail(self, payload: Any, job: Job) -> Job: ...
