"""A company's own website from its name, and a one-paragraph summary from
its homepage. Pure: no network. The name <-> domain check is inroad-sourcing's
(app/discovery/company_candidates.py): it keeps a name search from resolving
to a namesake."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from inroad_lite.sourcing.domain.olostep import SearchHit

# Registrable domains that are never a hiring company's own site.
THIRD_PARTY_DOMAINS = frozenset(
    {
        "linkedin.com", "indeed.com", "glassdoor.com", "crunchbase.com", "wikipedia.org",
        "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "github.com",
        "medium.com", "bloomberg.com", "techcrunch.com", "forbes.com", "google.com",
        "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "ycombinator.com",
        "wellfound.com", "builtin.com", "pitchbook.com", "zoominfo.com", "reddit.com",
    }
)  # fmt: skip
_NAME_NOISE = frozenset(
    {
        "inc", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "gmbh", "ag",
        "sa", "bv", "plc", "the", "group", "holdings", "technologies", "technology", "labs",
        "hq", "software", "systems", "careers", "jobs",
    }
)  # fmt: skip
# Second-level labels under a country code: acme.co.uk, acme.com.pk.
_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "ac", "gov", "edu"})
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_LEFTOVER_LINK = re.compile(r"\]\([^)]*\)")
_SENTENCE_END = re.compile(r"[a-z0-9)][.!?](\s|$)")
# A short block built around a call to action is a banner, not a description.
_CALL_TO_ACTION = re.compile(
    r"\b(?:read|learn|see|find out)\s+(?:the|more)\b|\bannouncement\b|\bsign up\b"
    r"|\bget started\b|\bbook a demo\b|\bfree trial\b|\bregister now\b",
    re.I,
)
_BANNER_CHARS = 160
_SUMMARY_CHARS = 240


_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_NOT_PUBLIC = frozenset({"localhost", "local", "internal", "lan", "home", "test", "example"})


def research_target(value: str) -> str | None:
    """A public company domain from what a person typed ("https://www.acme.com/about"
    -> acme.com), or None: no IP addresses, ports, credentials or private names.
    Mirrors inroad-sourcing's research_target."""
    text = value.strip().lower()
    parts = urlsplit(text if "//" in text else f"//{text}")
    host = parts.hostname or ""
    if parts.username or parts.password or parts.port or not host:
        return None
    labels = host.split(".")
    if (
        len(labels) < 2
        or not all(_LABEL.match(label) for label in labels)
        or labels[-1].isdigit()
        or labels[-1] in _NOT_PUBLIC
    ):
        return None
    return registrable_domain(host)


def resolution_query(name: str) -> str:
    return f'"{name}" official website'


def registrable_domain(host: str) -> str | None:
    labels = [label for label in host.lower().strip(".").split(".") if label]
    if labels and labels[0] == "www":
        labels = labels[1:]
    if len(labels) < 2:
        return None
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def name_matches_domain(name: str, domain: str) -> bool:
    label = re.sub(r"[^a-z0-9]", "", domain.split(".")[0].lower())
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in _NAME_NOISE]
    if not label or not words:
        return False
    joined = "".join(words)
    if label == joined or (len(joined) >= 4 and joined in label):
        return True
    # "Acme Robotics" -> acme.com, "Linear" -> linear.app; the first word
    # alone has to be distinctive enough not to match by accident.
    return len(words[0]) >= 4 and (label == words[0] or label.startswith(words[0]))


def domain_from_urls(name: str, urls: list[str]) -> str | None:
    """A posting hosted on the company's own careers page names its site for
    free (opswat.com/jobs/..., esri.com/careers/...)."""
    for url in urls:
        domain = registrable_domain(urlsplit(url).hostname or "")
        if domain and domain not in THIRD_PARTY_DOMAINS and name_matches_domain(name, domain):
            return domain
    return None


def domain_from_hits(name: str, hits: list[SearchHit]) -> str | None:
    """The first result whose domain matches the name. A candidate, checked
    by name, never the first result taken on trust: for a short name it is
    often a namesake."""
    return domain_from_urls(name, [hit.url for hit in hits])


def summary_from_markdown(markdown: str, name: str = "") -> str | None:
    """A homepage paragraph that describes the company: the first real one
    that names it, else the first real one. Real means not a heading, a
    menu, a list of links, a cookie notice, a teaser headline (no full
    sentence) or mostly another script (a site can serve a localised page
    to the scraper)."""
    paragraphs = [p for p in map(_paragraph, re.split(r"\n\s*\n", markdown)) if p]
    if not paragraphs:
        return None
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in _NAME_NOISE]
    naming = next((p for p in paragraphs if words and words[0] in p.lower()), None)
    return _cut(naming or paragraphs[0])


def _paragraph(block: str) -> str | None:
    # A link whose text holds brackets leaves "](/path)" behind: drop it.
    plain = _LEFTOVER_LINK.sub("", _MARKDOWN_LINK.sub(r"\1", block)).replace("[", "")
    text = " ".join(plain.split())
    letters = [c for c in text if c.isalpha()]
    if (
        text.startswith(("#", "|", "-", "*", ">", "!"))
        or len(text) < 60
        or len(text.split()) < 8
        or "cookie" in text.lower()
        or block.count("](") > 3
        or not _SENTENCE_END.search(text)
        or sum(c.isascii() for c in letters) < 0.8 * len(letters)
        or (len(text) < _BANNER_CHARS and _CALL_TO_ACTION.search(text))
    ):
        return None
    return text


def _cut(text: str) -> str:
    if len(text) <= _SUMMARY_CHARS:
        return text
    head = text[:_SUMMARY_CHARS]
    end = head.rfind(". ")
    return head[: end + 1] if end > 80 else head.rstrip() + "..."
