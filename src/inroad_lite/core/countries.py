"""ISO 3166-1 alpha-2 codes from country names and codes, to read a profile's
location and the countries a posting names. Pure. Shared by api and
sourcing."""

from __future__ import annotations

import re

_NAMES = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AD": "Andorra", "AO": "Angola",
    "AG": "Antigua and Barbuda", "AR": "Argentina", "AM": "Armenia", "AU": "Australia",
    "AT": "Austria", "AZ": "Azerbaijan", "BS": "Bahamas", "BH": "Bahrain", "BD": "Bangladesh",
    "BB": "Barbados", "BY": "Belarus", "BE": "Belgium", "BZ": "Belize", "BJ": "Benin",
    "BT": "Bhutan", "BO": "Bolivia", "BA": "Bosnia and Herzegovina", "BW": "Botswana",
    "BR": "Brazil", "BN": "Brunei", "BG": "Bulgaria", "BF": "Burkina Faso", "BI": "Burundi",
    "CV": "Cape Verde", "KH": "Cambodia", "CM": "Cameroon", "CA": "Canada",
    "CF": "Central African Republic", "TD": "Chad", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "KM": "Comoros", "CG": "Congo", "CD": "Democratic Republic of the Congo",
    "CR": "Costa Rica", "CI": "Ivory Coast", "HR": "Croatia", "CU": "Cuba", "CY": "Cyprus",
    "CZ": "Czech Republic", "DK": "Denmark", "DJ": "Djibouti", "DM": "Dominica",
    "DO": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt", "SV": "El Salvador",
    "GQ": "Equatorial Guinea", "ER": "Eritrea", "EE": "Estonia", "SZ": "Eswatini",
    "ET": "Ethiopia", "FJ": "Fiji", "FI": "Finland", "FR": "France", "GA": "Gabon",
    "GM": "Gambia", "GE": "Georgia", "DE": "Germany", "GH": "Ghana", "GR": "Greece",
    "GD": "Grenada", "GT": "Guatemala", "GN": "Guinea", "GW": "Guinea-Bissau", "GY": "Guyana",
    "HT": "Haiti", "HN": "Honduras", "HK": "Hong Kong", "HU": "Hungary", "IS": "Iceland",
    "IN": "India", "ID": "Indonesia", "IR": "Iran", "IQ": "Iraq", "IE": "Ireland",
    "IL": "Israel", "IT": "Italy", "JM": "Jamaica", "JP": "Japan", "JO": "Jordan",
    "KZ": "Kazakhstan", "KE": "Kenya", "KI": "Kiribati", "KW": "Kuwait", "KG": "Kyrgyzstan",
    "LA": "Laos", "LV": "Latvia", "LB": "Lebanon", "LS": "Lesotho", "LR": "Liberia",
    "LY": "Libya", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg",
    "MO": "Macau", "MG": "Madagascar", "MW": "Malawi", "MY": "Malaysia", "MV": "Maldives",
    "ML": "Mali", "MT": "Malta", "MH": "Marshall Islands", "MR": "Mauritania",
    "MU": "Mauritius", "MX": "Mexico", "FM": "Micronesia", "MD": "Moldova", "MC": "Monaco",
    "MN": "Mongolia", "ME": "Montenegro", "MA": "Morocco", "MZ": "Mozambique",
    "MM": "Myanmar", "NA": "Namibia", "NR": "Nauru", "NP": "Nepal", "NL": "Netherlands",
    "NZ": "New Zealand", "NI": "Nicaragua", "NE": "Niger", "NG": "Nigeria",
    "KP": "North Korea", "MK": "North Macedonia", "NO": "Norway", "OM": "Oman",
    "PK": "Pakistan", "PW": "Palau", "PS": "Palestine", "PA": "Panama",
    "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru", "PH": "Philippines",
    "PL": "Poland", "PT": "Portugal", "PR": "Puerto Rico", "QA": "Qatar", "RO": "Romania",
    "RU": "Russia", "RW": "Rwanda", "KN": "Saint Kitts and Nevis", "LC": "Saint Lucia",
    "VC": "Saint Vincent and the Grenadines", "WS": "Samoa", "SM": "San Marino",
    "ST": "Sao Tome and Principe", "SA": "Saudi Arabia", "SN": "Senegal", "RS": "Serbia",
    "SC": "Seychelles", "SL": "Sierra Leone", "SG": "Singapore", "SK": "Slovakia",
    "SI": "Slovenia", "SB": "Solomon Islands", "SO": "Somalia", "ZA": "South Africa",
    "KR": "South Korea", "SS": "South Sudan", "ES": "Spain", "LK": "Sri Lanka", "SD": "Sudan",
    "SR": "Suriname", "SE": "Sweden", "CH": "Switzerland", "SY": "Syria", "TW": "Taiwan",
    "TJ": "Tajikistan", "TZ": "Tanzania", "TH": "Thailand", "TL": "Timor-Leste", "TG": "Togo",
    "TO": "Tonga", "TT": "Trinidad and Tobago", "TN": "Tunisia", "TR": "Turkey",
    "TM": "Turkmenistan", "TV": "Tuvalu", "UG": "Uganda", "UA": "Ukraine",
    "AE": "United Arab Emirates", "GB": "United Kingdom", "US": "United States",
    "UY": "Uruguay", "UZ": "Uzbekistan", "VU": "Vanuatu", "VA": "Vatican City",
    "VE": "Venezuela", "VN": "Vietnam", "YE": "Yemen", "ZM": "Zambia", "ZW": "Zimbabwe",
}  # fmt: skip
_ALIASES = {
    "uae": "AE", "u.a.e.": "AE", "emirates": "AE", "uk": "GB", "u.k.": "GB",
    "great britain": "GB", "britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB", "usa": "US", "u.s.": "US", "u.s.a.": "US",
    "united states of america": "US",
    "america": "US", "czechia": "CZ", "turkiye": "TR", "türkiye": "TR", "korea": "KR",
    "republic of korea": "KR", "russian federation": "RU", "viet nam": "VN",
    "cote d'ivoire": "CI", "côte d'ivoire": "CI", "the netherlands": "NL", "holland": "NL",
    "ksa": "SA", "kingdom of saudi arabia": "SA", "macao": "MO", "burma": "MM",
    "swaziland": "SZ", "cabo verde": "CV", "east timor": "TL",
}  # fmt: skip
# Also a US state: "Atlanta, Georgia" must not read as the country.
_AMBIGUOUS = frozenset({"georgia"})
# Hiring hubs whose name alone names one country. Ambiguous ones are left
# out on purpose: Hyderabad (India, Pakistan), Cambridge (UK, US), Birmingham,
# Portland, London Ontario aside (London reads as the UK).
_CITIES = {
    "london": "GB", "manchester": "GB", "edinburgh": "GB", "bristol": "GB", "glasgow": "GB",
    "berlin": "DE", "munich": "DE", "hamburg": "DE", "frankfurt": "DE", "cologne": "DE",
    "amsterdam": "NL", "rotterdam": "NL", "utrecht": "NL", "eindhoven": "NL", "paris": "FR",
    "lyon": "FR", "dublin": "IE", "madrid": "ES", "barcelona": "ES", "lisbon": "PT",
    "porto": "PT", "stockholm": "SE", "copenhagen": "DK", "oslo": "NO", "helsinki": "FI",
    "zurich": "CH", "geneva": "CH", "vienna": "AT", "warsaw": "PL", "krakow": "PL",
    "wroclaw": "PL", "prague": "CZ", "budapest": "HU", "bucharest": "RO", "athens": "GR",
    "milan": "IT", "rome": "IT", "brussels": "BE", "tallinn": "EE", "riga": "LV",
    "vilnius": "LT", "sofia": "BG", "belgrade": "RS", "kyiv": "UA", "toronto": "CA",
    "vancouver": "CA", "montreal": "CA", "ottawa": "CA", "calgary": "CA", "new york": "US",
    "new york city": "US", "nyc": "US", "san francisco": "US", "seattle": "US", "austin": "US",
    "boston": "US", "chicago": "US", "los angeles": "US", "denver": "US", "dubai": "AE",
    "abu dhabi": "AE", "riyadh": "SA", "jeddah": "SA", "doha": "QA", "kuwait city": "KW",
    "manama": "BH", "muscat": "OM", "cairo": "EG", "amman": "JO", "istanbul": "TR",
    "tel aviv": "IL", "lahore": "PK", "karachi": "PK", "islamabad": "PK", "rawalpindi": "PK",
    "faisalabad": "PK", "bangalore": "IN", "bengaluru": "IN", "mumbai": "IN", "delhi": "IN",
    "new delhi": "IN", "pune": "IN", "chennai": "IN", "gurgaon": "IN", "gurugram": "IN",
    "noida": "IN", "singapore": "SG", "tokyo": "JP", "seoul": "KR", "shanghai": "CN",
    "beijing": "CN", "shenzhen": "CN", "bangkok": "TH", "jakarta": "ID", "manila": "PH",
    "kuala lumpur": "MY", "ho chi minh city": "VN", "hanoi": "VN", "sydney": "AU",
    "melbourne": "AU", "auckland": "NZ", "sao paulo": "BR", "são paulo": "BR",
    "mexico city": "MX", "buenos aires": "AR", "bogota": "CO", "bogotá": "CO",
    "lagos": "NG", "nairobi": "KE", "cape town": "ZA", "johannesburg": "ZA",
}  # fmt: skip

_BY_NAME = (
    {name.lower(): code for code, name in _NAMES.items() if name.lower() not in _AMBIGUOUS}
    | _ALIASES
    | _CITIES
)
_SPLIT = re.compile(r"[,/|()\-–&;]")


def country_name(code: str) -> str | None:
    return _NAMES.get(code.upper())


def country_code(value: object) -> str | None:
    """An ISO code, a country name, a location ending in one ("Lahore,
    Pakistan", "Remote - United Kingdom"), or a hub city whose name alone
    names one country ("Amsterdam"), or failing those the last country a
    longer text names ("USA Remote"). None otherwise: other cities are not
    guessed."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) == 2 and text.isalpha():
        return text.upper() if text.upper() in _NAMES else None
    whole = _BY_NAME.get(text.lower())
    if whole:
        return whole
    for part in reversed(_SPLIT.split(text)):
        code = _BY_NAME.get(part.strip().lower())
        if code:
            return code
    return _last_named(text)


# Inside a longer location ("USA Remote", "San Mateo, CA United States",
# "Remote - US"). "America" alone is left out: "Latin America" is not the US.
_NOT_IN_TEXT = frozenset({"america"})
_IN_TEXT = re.compile(
    r"(?<![\w.])("
    + "|".join(
        re.escape(name)
        for name in sorted(_BY_NAME, key=len, reverse=True)
        if name not in _NOT_IN_TEXT
    )
    + r")(?![\w])",
    re.I,
)
# Upper case only, and only codes no word or US state shares: "CA" is California.
_CODES = {"US": "US", "USA": "US", "UK": "GB", "UAE": "AE", "KSA": "SA"}
_CODES_IN_TEXT = re.compile(r"(?<![\w.])(" + "|".join(_CODES) + r")(?![\w])")


def _last_named(text: str) -> str | None:
    """The country named last in `text` (a location ends with its country)."""
    found = [(m.start(), _BY_NAME[m.group(1).lower()]) for m in _IN_TEXT.finditer(text)]
    found += [(m.start(), _CODES[m.group(1)]) for m in _CODES_IN_TEXT.finditer(text)]
    return max(found)[1] if found else None
