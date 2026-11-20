"""The company's job board, from links on its own home and careers pages.
Pure. Mirrors inroad-sourcing's app/ats/references.py, for the three boards
inroad-lite reads. Only those two pages are trusted: other pages link to
partners' and customers' boards."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from inroad_lite.sourcing.domain.jobs import BoardRef

_GREENHOUSE = frozenset(
    {"boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"}
)
_LEVER = {"jobs.lever.co": None, "jobs.eu.lever.co": "eu"}
_ASHBY = frozenset({"jobs.ashbyhq.com"})


def boards_in(links: list[tuple[str, str]]) -> list[BoardRef]:
    found: list[BoardRef] = []
    for _, url in links:
        ref = board_of(url)
        if ref and ref not in found:
            found.append(ref)
    return found


def board_of(url: str) -> BoardRef | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    if host in _GREENHOUSE:
        # An embedded board names itself in ?for=: /embed/job_board?for=acme
        if segments[:1] == ["embed"]:
            tokens = parse_qs(parts.query).get("for", [])
            return BoardRef("greenhouse", tokens[0]) if tokens else None
        return BoardRef("greenhouse", segments[0]) if segments else None
    if host in _LEVER:
        return BoardRef("lever", segments[0], _LEVER[host]) if segments else None
    if host in _ASHBY:
        return BoardRef("ashby", segments[0]) if segments else None
    return None
