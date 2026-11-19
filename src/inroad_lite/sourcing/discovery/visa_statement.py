"""What a posting says about visa sponsorship and relocation. Pure and
deterministic: a phrase match with negation, never a guess. "Not stated" is
the answer whenever the text does not say it plainly. Copied from
inroad-sourcing's app/discovery/visa_statement.py."""

from __future__ import annotations

import re
from enum import StrEnum


class Statement(StrEnum):
    OFFERED = "offered"
    NOT_OFFERED = "not_offered"
    NOT_STATED = "not_stated"


_VISA = re.compile(
    r"visa[\s-]*(?:sponsorship|sponsor(?:ed|s)?|support|assistance)"
    r"|sponsor(?:ship)?\s+(?:a\s+|your\s+)?(?:work\s+)?visas?"
    r"|work\s+(?:permit|authori[sz]ation)\s+(?:sponsorship|support)",
    re.I,
)
_RELOCATION = re.compile(
    r"relocation\s+(?:package|support|assistance|bonus|allowance|budget|help)"
    r"|(?:help|support|assist)\w*\s+(?:you\s+)?(?:with\s+)?(?:your\s+)?relocat"
    r"|relocation\s+(?:is\s+)?(?:offered|provided|available|covered)",
    re.I,
)
_NEGATION = re.compile(
    r"\b(?:no|not|unable|cannot|can't|won't|will\s+not|do\s+not|don't|does\s+not|without"
    r"|isn't|is\s+not|are\s+not|aren't|never|nor)\b",
    re.I,
)
_WINDOW = 60


def visa_sponsorship(text: str | None) -> Statement:
    return _statement(text, _VISA)


def relocation_support(text: str | None) -> Statement:
    return _statement(text, _RELOCATION)


def _statement(text: str | None, pattern: re.Pattern[str]) -> Statement:
    """Any negated mention wins: "we offer relocation but not visa
    sponsorship" must not read as a visa offer."""
    if not text:
        return Statement.NOT_STATED
    found = Statement.NOT_STATED
    for match in pattern.finditer(text):
        sentence_start = max(text.rfind(".", 0, match.start()) + 1, match.start() - _WINDOW)
        before = text[sentence_start : match.start()]
        after = text[match.end() : match.end() + 25]
        if _NEGATION.search(before) or re.match(r"\s*(?:is\s+)?not\b", after, re.I):
            return Statement.NOT_OFFERED
        found = Statement.OFFERED
    return found
