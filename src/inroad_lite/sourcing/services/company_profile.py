"""A short "about" for a company: find its website, scrape the homepage
through Olostep, keep its first real paragraph. The site comes from a
posting on the company's own careers page when there is one (free), else
from one Olostep search checked against the name."""

from __future__ import annotations

from dataclasses import dataclass

from inroad_lite.sourcing.discovery.company_sites import (
    domain_from_hits,
    domain_from_urls,
    resolution_query,
    summary_from_markdown,
)
from inroad_lite.sourcing.domain.olostep import OlostepAuthError, OlostepError
from inroad_lite.sourcing.net.olostep import OlostepClient


@dataclass(frozen=True)
class CompanyProfile:
    name: str
    domain: str | None
    summary: str | None


async def company_profile(
    name: str, posting_urls: list[str], client: OlostepClient
) -> CompanyProfile:
    domain = domain_from_urls(name, posting_urls)
    try:
        if domain is None:
            domain = domain_from_hits(name, await client.search(resolution_query(name)))
        if domain is None:
            return CompanyProfile(name, None, None)
        markdown = await client.scrape(f"https://{domain}")
    except OlostepAuthError:
        raise
    except OlostepError:
        return CompanyProfile(name, domain, None)
    return CompanyProfile(name, domain, summary_from_markdown(markdown, name))
