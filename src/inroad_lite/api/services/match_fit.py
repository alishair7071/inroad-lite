"""Whether a proven posting fits this person: where they can work, their
level, and their role. Personal, so it lives in api and never in sourcing.
Pure. Ported from inroad-api's app/services/match_fit.py; simplified: no
places left out, no company-wide visa evidence, and skills count in the
score (match_score) instead of ruling a posting out.

Location, per work preference:
- onsite / hybrid: the posting is in the person's country;
- remote: a remote posting open to the person's country: it names that
  country, or a region or "worldwide" that includes it. A remote posting
  naming only other countries, or no place at all, does not fit;
- relocation: a posting in one of the person's chosen places (anywhere when
  none is chosen) that offers visa sponsorship or relocation support, and
  does not rule a visa out."""

from __future__ import annotations

import re
from dataclasses import dataclass

from inroad_lite.api.schemas.profile import Profile
from inroad_lite.core.countries import country_code, country_name
from inroad_lite.sourcing.schemas.company_discovery import PostingOut


def _codes(codes: str) -> frozenset[str]:
    return frozenset(codes.split())


_EUROPE = _codes(
    "AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT LV LI LT LU MT MD MC ME NL "
    "MK NO PL PT RO SM RS SK SI ES SE CH UA GB VA XK"
)
_MIDDLE_EAST = _codes("AE SA QA KW BH OM JO LB IL IQ IR SY YE PS EG TR")
_AFRICA = _codes(
    "DZ AO BJ BW BF BI CV CM CF TD KM CG CD CI DJ EG GQ ER SZ ET GA GM GH GN GW KE LS LR LY "
    "MG MW ML MR MU MA MZ NA NE NG RW ST SN SC SL SO ZA SS SD TZ TG TN UG ZM ZW"
)
_APAC = _codes(
    "PK IN BD LK NP BT MV AF CN HK MO TW JP KR KP MN SG MY ID PH VN TH KH LA MM BN TL AU NZ PG FJ"
)
_LATAM = _codes("MX GT BZ HN SV NI CR PA CU DO HT JM PR CO VE EC PE BO PY UY AR CL BR")
_NORTH_AMERICA = frozenset({"US", "CA"})
_EVERYWHERE = re.compile(r"\b(worldwide|anywhere|global|globally|international)\b", re.I)
_REGIONS: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (re.compile(r"\bemea\b", re.I), _EUROPE | _MIDDLE_EAST | _AFRICA),
    (re.compile(r"\b(europe|european union|eu)\b", re.I), _EUROPE),
    (re.compile(r"\b(middle east|mena|gcc|gulf)\b", re.I), _MIDDLE_EAST),
    (re.compile(r"\b(apac|asia[- ]pacific|asia|south asia)\b", re.I), _APAC),
    (re.compile(r"\b(latam|latin america|south america)\b", re.I), _LATAM),
    (re.compile(r"\b(north america|americas)\b", re.I), _NORTH_AMERICA | _LATAM),
)
_REMOTE = re.compile(r"\bremote\b|home[- ]based|work from home|\bwfh\b|distributed", re.I)

_JUNIOR = re.compile(r"\b(junior|jr\.?|intern|internship|graduate|entry[- ]level|trainee)\b", re.I)
_SENIOR = re.compile(r"\b(senior|sr\.?|lead)\b", re.I)
_STAFF = re.compile(r"\b(staff|principal|head of|director|vp|vice president|chief)\b", re.I)

# Role families. A posting whose family the person does not target is a
# different job, however many words it shares.
_FAMILIES: dict[str, re.Pattern[str]] = {
    "frontend": re.compile(r"front[- ]?end|\breact\b|\bui engineer\b|\bweb developer\b", re.I),
    "backend": re.compile(r"back[- ]?end|\bserver[- ]side\b|\bapi engineer\b", re.I),
    "fullstack": re.compile(r"full[- ]?stack", re.I),
    "mobile": re.compile(r"\bmobile\b|\bios\b|\bandroid\b|\bflutter\b|react native", re.I),
    "data_analysis": re.compile(
        r"\bdata analyst|\banalytics\b|business intelligence|\bbi\b|product analyst", re.I
    ),
    "data_engineering": re.compile(r"data engineer|analytics engineer|\betl\b", re.I),
    "ml": re.compile(
        r"machine learning|\bml\b|mlops|\bai engineer|data scientist|deep learning|\bnlp\b", re.I
    ),
    "devops": re.compile(
        r"devops|\bsre\b|site reliability|platform engineer|infrastructure|cloud engineer", re.I
    ),
    "qa": re.compile(r"\bqa\b|quality assurance|test engineer|\bsdet\b|automation tester", re.I),
    "security": re.compile(r"security|penetration|\bsoc\b", re.I),
    "embedded": re.compile(r"embedded|firmware|hardware|\bfpga\b", re.I),
    "design": re.compile(r"designer|\bux\b|ui/ux", re.I),
    "product": re.compile(r"product manager|product owner", re.I),
    "sales": re.compile(r"\bsales\b|account executive|business development", re.I),
    # Pre-sales, not software engineering: shares only "engineer".
    "sales_engineering": re.compile(
        r"\bsolutions? (engineer|architect|consultant)|\bsales engineer|pre-?sales", re.I
    ),
    "support": re.compile(
        r"\bsupport (engineer|specialist|analyst|agent)|technical support|it support|"
        r"customer (support|success)|help ?desk|service desk",
        re.I,
    ),
}
# Languages and frameworks a title can name. A title naming some, none of
# which the person lists, is a different stack ("PHP Developer" for Python).
_STACK = re.compile(
    r"(?<![\w.+#])(php|laravel|java|kotlin|scala|\.net|c#|ruby|rails|golang|go|python|"
    r"django|node\.?js|react|angular|vue|swift|flutter|salesforce|sap|wordpress|magento|"
    r"c\+\+|rust|elixir)(?![\w+#])",
    re.I,
)
_COMPATIBLE = {
    "fullstack": {"frontend", "backend"},
    "frontend": {"fullstack"},
    "backend": {"fullstack"},
}
_GENERIC_SOFTWARE = {"frontend", "backend", "fullstack", "data_engineering", "devops"}
# What a generic "Software Engineer" target takes: product engineering, not
# platform, DevOps or data work.
_GENERIC_TARGET_TAKES = {"frontend", "backend", "fullstack"}
_MANAGES = re.compile(
    r"\b(engineering|software|development|data|design|team)\s+manager\b|\bmanager,", re.I
)
_HEADS = re.compile(
    r"\b(engineer|developer|analyst|scientist|designer|manager|architect|programmer)\b", re.I
)
# One location field can list several places: "Berlin; London; Remote".
_PLACES = re.compile(r"\s*(?:;|\||•|\s/\s)\s*")


@dataclass(frozen=True)
class Fit:
    ok: bool
    reason: str


def fit(profile: Profile, posting: PostingOut, *, relaxed: bool = False) -> Fit:
    """The location verdict carries the reason shown for a match. Relaxed
    keeps only the role rules: location and level are not checked."""
    where = location_fit(profile, posting)
    if relaxed:
        role = role_fit(profile, posting)
        if not role.ok:
            return role
        return where if where.ok else Fit(True, f"{_place(posting)} (location not checked)")
    if not where.ok:
        return where
    for check in (seniority_fit, role_fit):
        verdict = check(profile, posting)
        if not verdict.ok:
            return verdict
    return where


def location_fit(profile: Profile, posting: PostingOut) -> Fit:
    home = country_code(profile.location or "")
    preferences = set(profile.work_preference)
    countries = _posting_countries(posting)
    place = _place(posting)
    remote = posting.workplace == "remote" or any(_REMOTE.search(p) for p in posting.locations)
    in_home = bool(home) and home in countries
    if preferences & {"onsite", "hybrid"} and in_home and posting.workplace != "remote":
        return Fit(True, f"{_mode(posting)} in {place}")
    if "remote" in preferences and remote and home and _open_to(posting, countries, home):
        return Fit(True, f"Remote, open to {country_name(home)} ({place})")
    offer = _relocation_offer(posting)
    if "relocation" in preferences and offer and _in_places(countries, profile.relocation_places):
        return Fit(True, f"{place}, with {offer}")
    return Fit(False, f"location {place} does not fit {', '.join(sorted(preferences)) or 'any'}")


def seniority_fit(profile: Profile, posting: PostingOut) -> Fit:
    years, title = profile.years_experience, posting.title
    if _STAFF.search(title) and (years is None or years < 7):
        return Fit(False, "staff-level role")
    if _JUNIOR.search(title) and years is not None and years >= 3:
        return Fit(False, "junior role")
    if _SENIOR.search(title) and years is not None and years < 3:
        return Fit(False, "senior role")
    return Fit(True, "")


def role_fit(profile: Profile, posting: PostingOut) -> Fit:
    # Managing people is a different job from doing the work.
    if _MANAGES.search(posting.title) and not any(_MANAGES.search(r) for r in profile.roles):
        return Fit(False, "management role")
    stack = {match.lower() for match in _STACK.findall(posting.title)}
    known = " ".join(profile.skills).lower()
    if stack and not any(re.search(rf"(?<![\w+#.]){re.escape(s)}(?![\w+#])", known) for s in stack):
        return Fit(False, "different stack")
    title_families = role_families(posting.title)
    target_families: set[str] = set()
    generic_target = False
    for role in profile.roles:
        families = role_families(role)
        target_families |= families
        generic_target = generic_target or (not families and bool(_HEADS.search(role)))
    allowed = set(target_families)
    for family in target_families:
        allowed |= _COMPATIBLE.get(family, set())
    if generic_target:
        allowed |= _GENERIC_TARGET_TAKES
    if title_families:
        if title_families & allowed:
            return Fit(True, "")
        return Fit(False, f"{', '.join(sorted(title_families))} role")
    # A title with no specialty ("Software Engineer") fits a generic or a
    # general software target, not a specialist one.
    if not (generic_target or target_families & _GENERIC_SOFTWARE):
        return Fit(False, "generic role for a specialist target")
    title_heads = {h.lower() for h in _HEADS.findall(posting.title)}
    target_heads = {h.lower() for role in profile.roles for h in _HEADS.findall(role)}
    if title_heads & target_heads:
        return Fit(True, "")
    return Fit(False, "different role")


def role_families(text: str) -> set[str]:
    return {name for name, pattern in _FAMILIES.items() if pattern.search(text)}


def level(title: str) -> str:
    """junior, mid, senior or staff, by the same words seniority_fit reads."""
    if _STAFF.search(title):
        return "staff"
    if _SENIOR.search(title):
        return "senior"
    if _JUNIOR.search(title):
        return "junior"
    return "mid"


def _place(posting: PostingOut) -> str:
    return "; ".join(posting.locations) or country_name(posting.country or "") or "not stated"


def _posting_countries(posting: PostingOut) -> set[str]:
    places = [place for location in posting.locations for place in _PLACES.split(location)]
    codes = {code for code in map(country_code, places) if code}
    if posting.country:
        codes.add(posting.country.upper())
    return codes


def _open_to(posting: PostingOut, countries: set[str], home: str) -> bool:
    if home in countries:
        return True
    text = " ".join(posting.locations)
    if _EVERYWHERE.search(text):
        return True
    return any(pattern.search(text) and home in members for pattern, members in _REGIONS)


def _relocation_offer(posting: PostingOut) -> str | None:
    """Moving countries needs a visa: a stated "no visa sponsorship"
    outweighs any relocation help."""
    if posting.visa_sponsorship == "offered":
        return "visa sponsorship"
    if posting.visa_sponsorship == "not_offered":
        return None
    if posting.relocation_support == "offered":
        return "relocation support"
    return None


def _in_places(countries: set[str], places: list[str]) -> bool:
    if not places:
        return True
    allowed: set[str] = set()
    for place in places:
        if _EVERYWHERE.search(place):
            return True
        code = country_code(place)
        if code:
            allowed.add(code)
        for pattern, members in _REGIONS:
            if pattern.search(place):
                allowed |= members
    return bool(countries & allowed)


def _mode(posting: PostingOut) -> str:
    return {"hybrid": "Hybrid", "onsite": "Onsite"}.get(posting.workplace or "", "Based")
