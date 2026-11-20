"""Which of a site's own pages to read, from the links on its homepage. Pure.
Links are sorted into page kinds by their path and text, and the shortest
link of each kind wins."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from inroad_lite.sourcing.discovery.company_sites import registrable_domain
from inroad_lite.sourcing.domain.company_research import PageKind, SitePage

_LINK = re.compile(r"\[([^\]]{0,200})\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
_NOT_PAGES = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|pdf|zip|mp4|css|js)(\?|$)", re.I)
# In the order they are worth reading.
_KINDS: tuple[tuple[PageKind, frozenset[str]], ...] = (
    (PageKind.ABOUT, frozenset({"about", "about-us", "company", "who-we-are", "our-story"})),
    (
        PageKind.CAREERS,
        frozenset({"careers", "career", "jobs", "join", "join-us", "work-with-us", "hiring"}),
    ),
    (PageKind.PRODUCT, frozenset({"product", "products", "platform", "features", "solutions"})),
    (PageKind.TEAM, frozenset({"team", "people", "leadership", "founders"})),
    (PageKind.CUSTOMERS, frozenset({"customers", "case-studies", "clients", "customer-stories"})),
    (PageKind.NEWS, frozenset({"blog", "news", "press", "newsroom"})),
)


def links_in(markdown: str, base_url: str) -> list[tuple[str, str]]:
    """(link text, absolute URL) for every link in a page, in order, once."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text, href in _LINK.findall(markdown):
        href = href.strip("<>")
        if href.startswith(("mailto:", "tel:", "#", "javascript:")) or _NOT_PAGES.search(href):
            continue
        url = urljoin(base_url, href).split("#")[0]
        if urlsplit(url).scheme in ("http", "https") and url not in seen:
            seen.add(url)
            found.append((" ".join(text.split()), url))
    return found


def kind_of(url: str, text: str) -> PageKind | None:
    segments = [s.lower() for s in urlsplit(url).path.split("/") if s]
    label = text.strip().lower().replace(" ", "-")
    for kind, words in _KINDS:
        if (segments and segments[0] in words) or label in words:
            return kind
    return None


def pick_pages(links: list[tuple[str, str]], domain: str, *, limit: int) -> list[SitePage]:
    """The site's own pages worth reading: one per kind, the shortest link
    of that kind, most useful kinds first."""
    best: dict[PageKind, str] = {}
    for text, url in links:
        parts = urlsplit(url)
        if registrable_domain(parts.hostname or "") != domain:
            continue
        depth = len([s for s in parts.path.split("/") if s])
        kind = kind_of(url, text)
        if kind is None or depth == 0 or depth > 2:
            continue
        if kind not in best or len(url) < len(best[kind]):
            best[kind] = url
    ordered = [SitePage(best[kind], kind) for kind, _ in _KINDS if kind in best]
    return ordered[:limit]
