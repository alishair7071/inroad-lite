"""Company discovery parsing: search queries from a request, and candidate
companies from search hits. Pure: no network. Only the job boards the
queries ask for are read. Precision over recall: a hit whose employer cannot be read
off its URL is rejected, never guessed."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from inroad_lite.sourcing.domain.company_discovery import (
    Candidate,
    DiscoveryRequest,
    PostingLead,
    RejectReason,
)
from inroad_lite.sourcing.domain.olostep import SearchHit

_ATS_HOSTS = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.eu.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
}
_EU_HOSTS = frozenset({"jobs.eu.lever.co"})
_GREENHOUSE_JOB = re.compile(r"/jobs/(\d+)")
# Postings on these boards name the employer in their URL, so a hit resolves
# to a company without guessing.
ATS_QUERY = (
    "(site:boards.greenhouse.io OR site:job-boards.greenhouse.io"
    " OR site:jobs.lever.co OR site:jobs.ashbyhq.com)"
)
_ROLE_AT = re.compile(
    r"^(?:job application for )?(?P<role>.+?) (?:at|@) (?P<company>[^|•\-–]+)", re.I
)
_LEVER = re.compile(r"^(?P<company>[^-–|]+?)\s+[-–]\s+(?P<role>.+)$")
# Job sites that run their own board on an ATS: the postings are other
# companies' roles.
_AGGREGATOR_TOKENS = frozenset(
    {
        "jobgether", "himalayas", "remoteok", "weworkremotely", "flexjobs", "bebee",
        "jooble", "adzuna", "jobrapido", "talentcom", "ziprecruiter", "simplyhired",
        "careerbuilder", "workshub", "remoteco", "dice", "otta", "builtin", "wellfound",
    }
)  # fmt: skip
_MAX_FIELD = 120


def build_queries(request: DiscoveryRequest, *, limit: int) -> list[str]:
    """ATS-restricted queries, one per (role, work mode), up to `limit`. The
    first round gives each role the next mode in turn, then each role's
    other modes follow, so a few searches still cover every mode. Skills
    rotate across queries. The wording was chosen by testing searches live: remote asks
    for postings open anywhere or in the person's country, onsite asks for
    the place with no skill (skills there returned nothing), relocation asks
    for a stated visa or relocation offer."""
    city = request.locations[0] if request.locations else None
    country = request.locations[1] if len(request.locations) > 1 else None
    modes = _modes(request)
    roles = list(request.roles)
    first = [(index, modes[index % len(modes)]) for index in range(len(roles))]
    rest = [
        (index, mode) for index in range(len(roles)) for mode in modes if (index, mode) not in first
    ]
    queries: list[str] = []
    for count, (index, mode) in enumerate([*first, *rest][:limit]):
        place, skill_count = _place(mode, city, country, request.relocation_places)
        skills = " ".join(_rotate(request.keywords, start=count, count=skill_count))
        parts = [f'"{roles[index]}"', skills, place, ATS_QUERY]
        query = " ".join(part for part in parts if part).strip()
        if query not in queries:
            queries.append(query)
    return queries


def candidate_from_hit(hit: SearchHit, *, roles: tuple[str, ...]) -> Candidate | RejectReason:
    parts = urlsplit(hit.url)
    host = (parts.hostname or "").lower()
    provider = _ATS_HOSTS.get(host)
    if provider is None or parts.scheme not in ("http", "https"):
        return RejectReason.NOT_A_BOARD
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        return RejectReason.UNIDENTIFIED_EMPLOYER
    token = segments[0]
    if _is_aggregator(token):
        return RejectReason.AGGREGATOR
    title = _clean(hit.title)
    posting = posting_id(provider, hit.url)
    role, company = _ats_title(title, provider, roles)
    if posting is None:
        # A board's home page, usually titled with the company alone: the
        # board is searched for a matching posting once it is read.
        if role is None or not relevant_title(role, roles):
            role, company = None, company or (title.split("|")[0].strip() if title else None)
    elif role is not None and not relevant_title(role, roles):
        return RejectReason.IRRELEVANT
    return Candidate(
        company_name=company or _from_token(token),
        ats_provider=provider,
        ats_token=token,
        ats_region="eu" if host in _EU_HOSTS else None,
        leads=[PostingLead(posting_id=posting, role_title=role, url=hit.url[:2048])],
    )


def posting_id(provider: str, url: str) -> str | None:
    """The posting an ATS URL points at, or None for the board's home page."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if provider in ("lever", "ashby"):
        return segments[1] if len(segments) > 1 else None
    if provider == "greenhouse":
        query_id = parse_qs(parts.query).get("gh_jid")
        if query_id and query_id[0].isdigit():
            return query_id[0]
        match = _GREENHOUSE_JOB.search(parts.path)
        return match.group(1) if match else None
    return None


def relevant_title(role_title: str, roles: tuple[str, ...]) -> bool:
    """Loose on purpose: any word longer than two letters of any target role.
    The strict role rules run later, in api's match fit."""
    title_words = set(re.findall(r"[a-z0-9+#]+", role_title.lower()))
    for role in roles:
        words = [w for w in re.findall(r"[a-z0-9+#]+", role.lower()) if len(w) > 2]
        if words and any(w in title_words for w in words):
            return True
    return False


def _modes(request: DiscoveryRequest) -> list[str | None]:
    modes: list[str | None] = []
    if request.remote:
        modes.append("remote")
    # A place with no stated preference is where the person works.
    if request.onsite or (request.locations and not request.remote and not request.relocation):
        modes.append("onsite")
    if request.relocation:
        modes.append("relocation")
    return modes or [None]


def _place(
    mode: str | None, city: str | None, country: str | None, relocation_places: tuple[str, ...]
) -> tuple[str, int]:
    """(place clause, how many skills go with it)."""
    if mode == "remote":
        home = country or city
        return f"remote (worldwide OR anywhere OR global{f' OR {home}' if home else ''})", 1
    if mode == "onsite" and city:
        return (f"({city} OR {country})" if country and country != city else city), 0
    if mode == "relocation":
        offer = '("visa sponsorship" OR relocation)'
        if relocation_places:
            return f"{offer} ({' OR '.join(relocation_places)})", 1
        return offer, 1
    return "", 2


def _rotate(items: tuple[str, ...], *, start: int, count: int) -> list[str]:
    if not items:
        return []
    return [items[(start + offset) % len(items)] for offset in range(min(count, len(items)))]


def _ats_title(
    title: str | None, provider: str, roles: tuple[str, ...]
) -> tuple[str | None, str | None]:
    if not title:
        return None, None
    match = _ROLE_AT.match(title)
    if match:
        return _clean(match["role"]), _clean(match["company"])
    if provider == "lever":
        match = _LEVER.match(title)
        if match:
            role, company = _clean(match["role"]), _clean(match["company"])
            # Lever's page reads "Company - Role"; search engines often show
            # "Role - Company". Whichever side names a target role is it.
            if (
                company
                and role
                and relevant_title(company, roles)
                and not relevant_title(role, roles)
            ):
                return company, role
            return role, company
    return _clean(title.split("|")[0]), None


def _is_aggregator(token: str) -> bool:
    return re.sub(r"[^a-z0-9]", "", token.lower()) in _AGGREGATOR_TOKENS


def _from_token(token: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", token) if part)[:_MAX_FIELD]


def _clean(value: str | None, limit: int = _MAX_FIELD) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip(" -|•·")
    return text[:limit] or None
