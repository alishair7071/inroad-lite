"""Small helpers every board reader shares. Pure."""

from __future__ import annotations

import html
import re
from typing import Any

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr)\b[^>]*>", re.I)
_MAX_DESCRIPTION = 8000
_WORKPLACES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on_site": "onsite",
    "in-office": "onsite",
}


def text(value: Any, limit: int = 300) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


def html_to_text(value: Any) -> str | None:
    """Markup to plain text, blocks kept apart, capped."""
    if not isinstance(value, str) or not value.strip():
        return None
    marked = _BLOCK.sub("\n", html.unescape(value))
    plain = html.unescape(_TAG.sub(" ", marked))
    lines = (" ".join(line.split()) for line in plain.splitlines())
    joined = "\n".join(line for line in lines if line)
    return joined[:_MAX_DESCRIPTION] or None


def workplace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _WORKPLACES.get(value.strip().lower().replace(" ", ""))


def remote_from_locations(locations: tuple[str, ...]) -> str | None:
    """Greenhouse has no workplace field: a location naming remote is one."""
    return "remote" if any("remote" in place.lower() for place in locations) else None


def places(values: list[Any]) -> tuple[str, ...]:
    found: list[str] = []
    for value in values:
        place = text(value, 120)
        if place and place not in found:
            found.append(place)
    return tuple(found)
