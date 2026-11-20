"""How well one open role fits the person, 0 to 100, with every part shown.
Pure and deterministic: no model call, and each point comes from a fact
that can be shown. Location is not scored: match_fit already left out every
role the person cannot work in. Ported from inroad-api's
app/services/match_score.py; simplified: a skill counts when the posting
names it (Inroad also weighs whether the person's work history shows it)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from inroad_lite.api.services import match_fit

WEIGHTS = {"role": 35, "skills": 40, "level": 10, "posted": 15}
STRONG, GOOD = 75, 55
# A title of a family the person targets, with few words in common.
_SAME_KIND = 0.5
# A part that cannot be checked counts as this: leaving it out would let a
# posting that says less outscore one that says more.
_UNKNOWN = 0.5
# This many of the person's skills named in the posting add the most.
_NAMED_ENOUGH = 3
_LEVELS = ("junior", "mid", "senior", "staff")
_COMPOUND = re.compile(r"\b(full|front|back)[\s-]+(stack|end)\b")
# (days since posted, share of the points): most applications come in the
# first days, and an engineering role fills in about two months.
_FRESHNESS = ((7, 1.0), (30, 0.8), (60, 0.5), (90, 0.2))


@dataclass(frozen=True)
class Part:
    name: str
    detail: str
    # 0 to 1; None when it could not be checked (it then counts as _UNKNOWN).
    value: float | None


@dataclass(frozen=True)
class MatchScore:
    score: int
    band: str
    parts: tuple[Part, ...]
    matched_skills: tuple[str, ...] = ()


def score_role(
    *,
    targets: list[str],
    skills: list[str],
    years: float | None,
    title: str,
    text: str,
    posted_at: str | None,
    location: str,
    now: datetime | None = None,
    described: bool = True,
) -> MatchScore:
    """`described` is False when only the title was read: skills it does not
    name are then unknown, not missing."""
    skill_part, matched = _skills(skills, text)
    if not described and not matched:
        skill_part = Part("Skills", "Posting text not read; counted as unknown", None)
    parts = [_role(targets, title), skill_part, _level(years, title), _posted(posted_at, now)]
    base = sum(
        WEIGHTS[part.name.lower()] * (_UNKNOWN if part.value is None else part.value)
        for part in parts
    )
    score = max(0, min(100, round(base)))
    shown = (*parts, Part("Location", location, 1.0))
    return MatchScore(score, band(score), shown, tuple(matched))


def score_company(best: MatchScore, fitting: int) -> int:
    """The best role first, then how many roles fit: a company hiring five
    people like you is a better bet than one hiring one."""
    roles = min(fitting, 5) / 5
    value = (0.7 * best.score / 100 + 0.15 * roles) / 0.85
    return max(0, min(100, round(100 * value)))


def band(score: int) -> str:
    return "strong" if score >= STRONG else "good" if score >= GOOD else "possible"


def closeness(title: str, targets: list[str]) -> float:
    """Share of a target role's words the title has, best target counting."""
    words = _words(title)
    return max(
        (len(words & _words(t)) / len(_words(t)) for t in targets if _words(t)),
        default=0.0,
    )


def _words(text: str) -> set[str]:
    """ "Full Stack", "full-stack" and "Fullstack" are one word here."""
    joined = _COMPOUND.sub(lambda m: m.group(1) + m.group(2), text.lower())
    return set(re.findall(r"[a-z0-9+#]+", joined))


def _role(targets: list[str], title: str) -> Part:
    best = max(targets, key=lambda target: closeness(title, [target]), default=None)
    near = closeness(title, targets)
    if best and near >= 1.0:
        return Part("Role", f"Matches your target {best}", 1.0)
    if best and near >= _SAME_KIND:
        return Part("Role", f"Close to your target {best}", near)
    return Part("Role", "The same kind of role as your targets", _SAME_KIND)


def _skills(skills: list[str], text: str) -> tuple[Part, list[str]]:
    lowered = text.lower()
    unique = {s.strip().lower(): s.strip() for s in reversed(skills) if s.strip()}
    found = [s for key, s in reversed(unique.items()) if _mentions(lowered, key)]
    if not found:
        return Part("Skills", "None of yours named in the posting", None), []
    value = _UNKNOWN + (1 - _UNKNOWN) * min(len(found), _NAMED_ENOUGH) / _NAMED_ENOUGH
    return Part("Skills", f"Names {', '.join(found[:4])}", value), found


def _mentions(text: str, skill: str) -> bool:
    return bool(re.search(rf"(?<![\w+#.]){re.escape(skill)}(?![\w+#])", text))


def _level(years: float | None, title: str) -> Part:
    level = match_fit.level(title)
    if years is None:
        return Part("Level", f"{level.capitalize()} level; your experience is not given", None)
    expected = _expected_level(years)
    gap = abs(_LEVELS.index(level) - _LEVELS.index(expected))
    fits = "fits" if gap == 0 else "a step from" if gap == 1 else "far from"
    return Part(
        "Level",
        f"{level.capitalize()} level, {fits} your {years:g} years",
        (1.0, 0.5, 0.0)[min(gap, 2)],
    )


def _expected_level(years: float) -> str:
    return "junior" if years < 2 else "mid" if years < 5 else "senior" if years < 8 else "staff"


def _posted(posted_at: str | None, now: datetime | None) -> Part:
    when = _parse(posted_at)
    if when is None:
        return Part("Posted", "Date not given", None)
    days = max(0, ((now or datetime.now(UTC)) - when).days)
    value = next((v for limit, v in _FRESHNESS if days <= limit), 0.0)
    when_said = "Today" if days == 0 else f"{days} day{'s' if days > 1 else ''} ago"
    return Part("Posted", when_said, value)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
