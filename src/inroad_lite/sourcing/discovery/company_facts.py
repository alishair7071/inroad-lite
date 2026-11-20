"""What a company's own pages say about it, read by rules. Pure. Inroad
reads its pages with an LLM; here each fact is a phrase pattern, kept only
when a sentence states it plainly, and always with that sentence as its
evidence. Precision over recall: a fact not stated this way is left out."""

from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urlsplit

from inroad_lite.sourcing.discovery.company_sites import summary_from_markdown
from inroad_lite.sourcing.domain.company_research import Fact

_MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_QUOTE_CHARS = 240

_Rule = tuple[str, re.Pattern[str], Callable[[re.Match[str], str], str]]
_RULES: tuple[_Rule, ...] = (
    (
        "Founded",
        # "founded in 2013", "Founded 2013", and a stats strip's "2013 Founded".
        re.compile(
            r"\b(?:founded|established)\s+(?:in\s+)?((?:19|20)\d{2})\b"
            r"|\b((?:19|20)\d{2})\s*(?:founded|established)\b",
            re.I,
        ),
        lambda m, _: f"Founded in {m[1] or m[2]}",
    ),
    (
        "Headquarters",
        re.compile(
            r"\b(?:headquartered|headquarters)\s+(?:is\s+)?in\s+"
            r"([A-Z][A-Za-z.'-]+(?:(?:,\s*|\s)[A-Z][A-Za-z.'-]+){0,3})"
        ),
        lambda m, _: f"Headquartered in {m[1].rstrip('.')}",
    ),
    (
        "Team size",
        # "a team of 200 people", "We're 750+ people", "over 500 employees",
        # "750+ team members". "Over 10,000 people use it" is users, not
        # staff: plain "people" counts only after "we're" or "team of".
        re.compile(
            r"\b(?:we['’]re|we are|team of)\s+(\d[\d,]*\+?)\s+"
            r"(?:people|employees|engineers|team members|staff|teammates)\b"
            r"|\b(?:over|more than|nearly|almost)\s+(\d[\d,]*\+?)\s+"
            r"(?:employees|engineers|team members|staff|teammates)\b"
            r"|\b(\d[\d,]*\+?)\s*(?:team members|employees)\b",
            re.I,
        ),
        lambda m, _: f"{m[1] or m[2] or m[3]} people",
    ),
    (
        "Funding",
        re.compile(
            r"\b(?:raised|raising)\b[^.]{0,60}?(\$\s?\d[\d.,]*\s?(?:billion|million|bn|[mb])\b)",
            re.I,
        ),
        lambda m, _: f"Raised {m[1]}",
    ),
    (
        "Customers",
        # "650+ customers" counts; otherwise the sentence naming who uses it.
        re.compile(
            r"\b(\d[\d,]*\+?)\s*customers\b|\b(?:trusted by|used by|customers include|loved by)\b",
            re.I,
        ),
        lambda m, sentence: f"{m[1]} customers" if m[1] else sentence,
    ),
)
_SOCIAL = (
    ("LinkedIn", re.compile(r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[\w.-]+/?$", re.I)),
    ("GitHub", re.compile(r"^https?://(?:www\.)?github\.com/[\w.-]+/?$", re.I)),
    ("X / Twitter", re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/\w+/?$", re.I)),
)


def overview(markdown: str, name: str, url: str) -> Fact | None:
    summary = summary_from_markdown(markdown, name)
    return Fact("Overview", summary, summary, url) if summary else None


def facts_from_pages(pages: list[tuple[str, str]]) -> list[Fact]:
    """(url, markdown) pages in order; the first page stating each kind of
    fact wins, so the homepage and about page come first."""
    found: dict[str, Fact] = {}
    for url, markdown in pages:
        for sentence in sentences(markdown):
            for category, pattern, label in _RULES:
                if category in found:
                    continue
                match = pattern.search(sentence)
                if match:
                    found[category] = Fact(category, label(match, sentence), sentence, url)
    return [found[category] for category, _, _ in _RULES if category in found]


def social_links(links: list[tuple[str, str]], source_url: str) -> list[Fact]:
    found: list[Fact] = []
    for label, pattern in _SOCIAL:
        url = next((u for _, u in links if pattern.match(u)), None)
        if url:
            found.append(Fact(label, url.rstrip("/"), url, source_url))
    return found


def company_name(markdown: str, domain: str) -> str:
    """The homepage's first heading when it is short enough to be a name,
    else the domain."""
    for line in markdown.splitlines():
        heading = re.match(r"^#\s+(.+)$", line.strip())
        if heading:
            text = _MARKDOWN_LINK.sub(r"\1", heading[1]).strip()
            if 1 <= len(text.split()) <= 3 and len(text) <= 40:
                return text
            break
    label = domain.split(".")[0]
    return label[:1].upper() + label[1:]


def sentences(markdown: str) -> list[str]:
    """Prose sentences: links reduced to their text, headings, list markers,
    tables and image lines dropped."""
    lines = []
    for raw in markdown.splitlines():
        line = _MARKDOWN_LINK.sub(r"\1", raw).strip()
        if not line or line.startswith(("#", "|", "!", ">")):
            continue
        lines.append(re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", line))
    text = " ".join(" ".join(lines).split())
    return [_cap(s) for s in _SENTENCE_SPLIT.split(text) if len(s.split()) >= 3]


def page_label(url: str) -> str:
    path = urlsplit(url).path.strip("/")
    return path or "home"


def _cap(sentence: str) -> str:
    return sentence if len(sentence) <= _QUOTE_CHARS else sentence[: _QUOTE_CHARS - 3] + "..."
