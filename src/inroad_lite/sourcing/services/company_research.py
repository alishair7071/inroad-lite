"""Research one company from its own website. Mirrors the steps of
inroad-sourcing's research run: discover the site's pages from the
homepage, read them, extract what they say with evidence, and read the
company's job board. Pages are read with Olostep scrapes; the facts come
from rules (discovery/company_facts.py), where Inroad uses an LLM."""

from __future__ import annotations

import asyncio

from inroad_lite.sourcing.ats.base import MalformedListing
from inroad_lite.sourcing.ats.registry import ADAPTERS
from inroad_lite.sourcing.discovery.board_links import boards_in
from inroad_lite.sourcing.discovery.company_facts import (
    company_name,
    facts_from_pages,
    overview,
    social_links,
)
from inroad_lite.sourcing.discovery.company_sites import name_matches_domain
from inroad_lite.sourcing.discovery.website_pages import links_in, pick_pages
from inroad_lite.sourcing.domain.company_research import (
    DEFAULT_RESEARCH_POLICY,
    CompanyResearch,
    PageKind,
    ResearchPolicy,
    SitePage,
)
from inroad_lite.sourcing.domain.jobs import BoardRef, BoardScan
from inroad_lite.sourcing.domain.olostep import OlostepAuthError, OlostepError
from inroad_lite.sourcing.net.fetcher import FetchError
from inroad_lite.sourcing.net.olostep import OlostepClient
from inroad_lite.sourcing.services.candidate_proof import JsonFetcher, with_facts


class SiteUnreadable(Exception):
    """The homepage could not be read: there is nothing to research."""


async def research_company(
    domain: str,
    client: OlostepClient,
    fetcher: JsonFetcher,
    policy: ResearchPolicy = DEFAULT_RESEARCH_POLICY,
) -> CompanyResearch:
    home_url = f"https://{domain}"
    try:
        home = await client.scrape(home_url)
    except OlostepAuthError:
        raise
    except OlostepError as exc:
        raise SiteUnreadable(str(exc)) from None

    home_links = links_in(home, home_url)
    chosen = pick_pages(home_links, domain, limit=policy.max_pages)
    results = await asyncio.gather(
        *(client.scrape(page.url) for page in chosen), return_exceptions=True
    )
    read: list[tuple[SitePage, str]] = [(SitePage(home_url, PageKind.HOME), home)]
    for page, result in zip(chosen, results, strict=True):
        if isinstance(result, OlostepAuthError):
            raise result
        if isinstance(result, str):
            read.append((page, result))  # a page that fails to read is skipped

    name = company_name(home, domain)
    research = CompanyResearch(domain=domain, name=name, summary=None)
    research.pages_read = [page for page, _ in read]
    # The about page describes the company; a homepage often leads with a
    # product announcement.
    about = [(p.url, md) for p, md in read if p.kind is PageKind.ABOUT]
    first = next(
        (fact for url, md in [*about, (home_url, home)] if (fact := overview(md, name, url))),
        None,
    )
    research.summary = first.text if first else None
    research.facts = [
        *([first] if first else []),
        *facts_from_pages([(page.url, markdown) for page, markdown in read]),
        *social_links(home_links, home_url),
    ]

    # Board links are only trusted on the home and careers pages.
    trusted = [
        link
        for page, markdown in read
        if page.kind in (PageKind.HOME, PageKind.CAREERS)
        for link in links_in(markdown, page.url)
    ]
    boards = boards_in(trusted)
    if boards:
        scan = await _read(fetcher, boards[0])
        if scan is None:
            research.job_board = boards[0]
            research.board_note = "the job board linked from the site could not be read"
            return research
        board, how = boards[0], "linked from the site"
    else:
        # Many careers pages load their board in the browser, out of reach of
        # a scrape. Boards are usually named after the company: a board named
        # after the site counts only once its own data shows it is this company.
        found = await _named_board(fetcher, domain)
        if found is None:
            research.board_note = "no Greenhouse, Lever or Ashby board found for the site"
            return research
        board, scan, how = found
    research.job_board = board
    research.board_note = how
    research.openings = [with_facts(job) for job in scan.jobs]
    if scan.company_name:
        research.name = scan.company_name
    return research


async def _read(fetcher: JsonFetcher, board: BoardRef) -> BoardScan | None:
    adapter = ADAPTERS[board.provider]
    try:
        payload = await fetcher.get_json(
            adapter.listing_url(board), allowed_hosts=adapter.hosts(board)
        )
        return adapter.parse_listing(payload)
    except (FetchError, MalformedListing):
        return None


async def _named_board(fetcher: JsonFetcher, domain: str) -> tuple[BoardRef, BoardScan, str] | None:
    label = domain.split(".")[0]
    for board in (
        BoardRef("greenhouse", label),
        BoardRef("lever", label),
        BoardRef("ashby", label),
    ):
        scan = await _read(fetcher, board)
        if scan is None or not scan.jobs:
            continue
        if scan.company_name and name_matches_domain(scan.company_name, domain):
            return (
                board,
                scan,
                f"named after the site; the board names the company {scan.company_name}",
            )
        if not scan.company_name and any(
            domain in (job.description or "").lower() for job in scan.jobs
        ):
            return board, scan, f"named after the site; its job descriptions mention {domain}"
    return None
