from __future__ import annotations

import asyncio

import httpx
import pytest

from inroad_lite.sourcing.discovery.board_links import board_of
from inroad_lite.sourcing.discovery.company_facts import (
    company_name,
    facts_from_pages,
    social_links,
)
from inroad_lite.sourcing.discovery.company_sites import research_target
from inroad_lite.sourcing.discovery.website_pages import links_in, pick_pages
from inroad_lite.sourcing.domain.company_research import PageKind
from inroad_lite.sourcing.domain.jobs import BoardRef
from inroad_lite.sourcing.services.company_research import SiteUnreadable, research_company
from tests.support.fake_boards import (
    FakeBoards,
    ashby_listing,
    ashby_url,
    greenhouse_listing,
    greenhouse_url,
    lever_url,
)
from tests.support.fake_olostep import FakeOlostep

HOME = """# Acme

Acme builds developer tools that help small teams ship backend services faster.

[About](/about) [Careers](https://acme.com/careers/) [Pricing](/pricing)
[Product](https://www.acme.com/product) [Blog post](/blog/2026/11/a-long-post)
[Partner](https://partner.example.org/about) ![logo](/logo.png) [Mail](mailto:hi@acme.com)
[LinkedIn](https://www.linkedin.com/company/acme/) [GitHub](https://github.com/acme)
"""
ABOUT = """# About us

Acme was founded in 2016 and is headquartered in Berlin, Germany. We're 120+ people.
Our tools are trusted by 4,000 engineering teams. We raised $40M in our Series B.
"""
CAREERS = "# Careers\n\nSee our [open roles](https://job-boards.greenhouse.io/acmehq).\n"


# Which pages to read


def test_links_are_made_absolute_and_non_pages_dropped():
    urls = [url for _, url in links_in(HOME, "https://acme.com")]
    assert "https://acme.com/about" in urls
    assert not any(u.endswith(".png") or u.startswith("mailto:") for u in urls)


def test_one_page_of_each_kind_is_picked_from_the_site_itself():
    pages = pick_pages(links_in(HOME, "https://acme.com"), "acme.com", limit=4)
    assert [(p.kind, p.url) for p in pages] == [
        (PageKind.ABOUT, "https://acme.com/about"),
        (PageKind.CAREERS, "https://acme.com/careers/"),
        (PageKind.PRODUCT, "https://www.acme.com/product"),
    ]


# What the pages say


def test_facts_are_read_with_the_sentence_and_page_that_state_them():
    facts = {f.category: f for f in facts_from_pages([("https://acme.com/about", ABOUT)])}
    assert facts["Founded"].text == "Founded in 2016"
    assert facts["Headquarters"].text == "Headquartered in Berlin, Germany"
    assert facts["Team size"].text == "120+ people"
    assert facts["Funding"].text == "Raised $40M"
    assert facts["Customers"].quote.startswith("Our tools are trusted by")
    assert all(f.source_url == "https://acme.com/about" for f in facts.values())


@pytest.mark.parametrize(
    ("text", "category", "found"),
    [
        ("2013Founded in New York City 650+Customers across brands.", "Founded", "Founded in 2013"),
        ("650+Customers across brands and investors worldwide.", "Customers", "650+ customers"),
        ("Our 750+ team members work across the globe today.", "Team size", "750+ people"),
        ("Over 10,000 people use the app every single day.", "Team size", None),
    ],
)
def test_real_phrasings_and_one_that_is_not_staff(text, category, found):
    facts = {f.category: f.text for f in facts_from_pages([("https://x.com", text)])}
    assert facts.get(category) == found


def test_social_links_and_name():
    links = links_in(HOME, "https://acme.com")
    labels = {f.category: f.text for f in social_links(links, "https://acme.com")}
    assert labels == {
        "LinkedIn": "https://www.linkedin.com/company/acme",
        "GitHub": "https://github.com/acme",
    }
    assert company_name(HOME, "acme.com") == "Acme"
    assert company_name("# The fastest way to ship\n", "acme.com") == "Acme"


# Boards and domains


@pytest.mark.parametrize(
    ("url", "board"),
    [
        ("https://job-boards.greenhouse.io/acmehq/jobs/1", BoardRef("greenhouse", "acmehq")),
        (
            "https://boards.greenhouse.io/embed/job_board?for=acmehq",
            BoardRef("greenhouse", "acmehq"),
        ),
        ("https://jobs.eu.lever.co/acme", BoardRef("lever", "acme", "eu")),
        ("https://jobs.ashbyhq.com/acme/123", BoardRef("ashby", "acme")),
        ("https://acme.com/careers", None),
    ],
)
def test_board_links(url, board):
    assert board_of(url) == board


@pytest.mark.parametrize(
    ("typed", "domain"),
    [
        ("https://www.Acme.com/about", "acme.com"),
        ("acme.co.uk", "acme.co.uk"),
        ("localhost", None),
        ("10.0.0.1", None),
        ("acme.com:8080", None),
        ("user:pass@acme.com", None),
        ("acme", None),
    ],
)
def test_only_public_company_websites_are_researched(typed, domain):
    assert research_target(typed) == domain


# The whole research


def olostep(pages: dict[str, str]) -> FakeOlostep:
    def respond(payload: dict[str, object]) -> httpx.Response:
        url = str(payload["url_to_scrape"])
        if url not in pages:
            return httpx.Response(500)
        body = {"credits_consumed": 1, "result": {"markdown_content": pages[url]}}
        return httpx.Response(200, json=body)

    return FakeOlostep(respond)


def research(pages: dict[str, str], boards: FakeBoards, domain: str = "acme.com"):  # type: ignore[no-untyped-def]
    fake = olostep(pages)

    async def go():  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            return await research_company(domain, client, boards), client.usage

    return asyncio.run(go())


SITE = {
    "https://acme.com": HOME,
    "https://acme.com/about": ABOUT,
    "https://acme.com/careers/": CAREERS,
    # the product page fails to read and is skipped
}


def test_a_board_linked_from_the_careers_page_lists_the_open_roles():
    boards = FakeBoards(
        {
            greenhouse_url("acmehq"): greenhouse_listing(
                "acmehq", [(1, "Backend Engineer", "Remote"), (2, "Designer", "Berlin")], "Acme Inc"
            )
        }
    )
    found, usage = research(SITE, boards)
    assert found.name == "Acme Inc"
    assert found.summary.startswith("Acme was founded in 2016")  # the about page first
    assert [p.kind for p in found.pages_read] == [PageKind.HOME, PageKind.ABOUT, PageKind.CAREERS]
    assert found.board_note == "linked from the site"
    assert [job.title for job in found.openings] == ["Backend Engineer", "Designer"]
    assert {f.category for f in found.facts} >= {"Overview", "Founded", "LinkedIn"}
    assert (usage.calls, usage.credits) == (5, 3)  # one failed page tried twice


def test_with_no_board_link_a_board_named_after_the_site_needs_proof():
    no_link = {**SITE, "https://acme.com/careers/": "# Careers\n\nJobs load in your browser.\n"}
    named = FakeBoards(
        {greenhouse_url("acme"): greenhouse_listing("acme", [(1, "Backend Engineer", "x")], "Acme")}
    )
    found, _ = research(no_link, named)
    assert found.job_board == BoardRef("greenhouse", "acme")
    assert found.board_note == "named after the site; the board names the company Acme"

    namesake = FakeBoards(
        {greenhouse_url("acme"): greenhouse_listing("acme", [(1, "Engineer", "x")], "Zeta Corp")}
    )
    found, _ = research(no_link, namesake)
    assert found.job_board is None and found.openings == []
    assert found.board_note == "no Greenhouse, Lever or Ashby board found for the site"


def test_a_lever_or_ashby_board_is_trusted_only_if_its_jobs_mention_the_site():
    no_link = {**SITE, "https://acme.com/careers/": "# Careers\n"}
    listing = ashby_listing("acme", [("a1", "Backend Engineer")])
    listing["jobs"][0]["descriptionPlain"] = "Join us at acme.com to build tools."
    found, _ = research(no_link, FakeBoards({ashby_url("acme"): listing}))
    assert found.job_board == BoardRef("ashby", "acme")
    assert lever_url("acme")  # checked before ashby, absent here


def test_a_homepage_that_cannot_be_read_stops_the_research():
    with pytest.raises(SiteUnreadable):
        research({}, FakeBoards({}))
