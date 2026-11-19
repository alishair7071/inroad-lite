from __future__ import annotations

import asyncio

import httpx

from inroad_lite.sourcing.discovery.company_sites import (
    domain_from_urls,
    name_matches_domain,
    registrable_domain,
    summary_from_markdown,
)
from inroad_lite.sourcing.discovery.visa_statement import Statement, visa_sponsorship
from inroad_lite.sourcing.services.company_profile import company_profile
from tests.support.fake_olostep import FakeOlostep, search_body

ABOUT = "Acme makes reusable rockets so small teams can reach orbit without a launch budget."


def test_a_name_matches_only_its_own_domain():
    assert name_matches_domain("Acme Robotics Inc", "acmerobotics.com")
    assert name_matches_domain("Linear", "linear.app")
    # Too short to trust on its own, so a longer domain does not match.
    assert not name_matches_domain("Ro", "rover.com")
    assert not name_matches_domain("Acme", "example.com")
    assert registrable_domain("www.careers.acme.co.uk") == "acme.co.uk"


def test_a_posting_on_the_companys_own_site_names_it_for_free():
    urls = [
        "https://job-boards.greenhouse.io/opswat/jobs/1",
        "https://www.opswat.com/jobs/4620834005?gh_jid=4620834005",
    ]
    assert domain_from_urls("OPSWAT", urls) == "opswat.com"
    assert domain_from_urls("OPSWAT", urls[:1]) is None


def test_the_summary_is_the_first_real_paragraph():
    markdown = (
        "# Acme\n\n[Home](/) [Pricing](/p) [Blog](/b) [Docs](/d) [Login](/l)\n\n"
        "We use cookies to improve your experience on this website, as explained below.\n\n"
        "Featured Accelerating growth and agility for a bank with a mission critical platform\n\n"
        "Acme builds [developer tools](/tools) that help small teams ship backend services.\n"
    )
    assert summary_from_markdown(markdown) == (
        "Acme builds developer tools that help small teams ship backend services."
    )


def test_a_paragraph_naming_the_company_wins_and_other_scripts_are_skipped():
    markdown = (
        "Резервы обеспечены в соотношении 1:1 и доступны для проверки пользователями сервиса.\n\n"
        "Don't invest unless you're prepared to lose all the money you invest in this.\n\n"
        "BVNK is the payments infrastructure that lets businesses move money in stablecoins.\n"
    )
    assert summary_from_markdown(markdown, "BVNK") == (
        "BVNK is the payments infrastructure that lets businesses move money in stablecoins."
    )
    assert summary_from_markdown(markdown, "Acme").startswith("Don't invest")


def test_a_visa_offer_is_read_and_a_negated_one_is_not():
    assert visa_sponsorship("We offer visa sponsorship for this role.") is Statement.OFFERED
    assert visa_sponsorship("We cannot provide visa sponsorship.") is Statement.NOT_OFFERED
    assert visa_sponsorship("Great benefits.") is Statement.NOT_STATED


def test_a_company_profile_searches_only_when_no_posting_names_the_site():
    def respond(payload: dict[str, object]) -> httpx.Response:
        if "url_to_scrape" in payload:
            body = {"result": {"markdown_content": ABOUT}}
            return httpx.Response(200, json={"credits_consumed": 1, **body})
        hits = [{"url": "https://acme.example.org/"}, {"url": "https://www.acme.com/"}]
        return httpx.Response(200, json=search_body(hits))

    fake = FakeOlostep(respond)

    async def go(urls: list[str]):  # type: ignore[no-untyped-def]
        async with fake.client() as client:
            return await company_profile("Acme", urls, client)

    found = asyncio.run(go(["https://jobs.lever.co/acme/1"]))
    assert (found.domain, found.summary) == ("acme.com", ABOUT)
    assert [list(r)[0] for r in fake.requests] == ["query", "url_to_scrape"]

    fake.requests.clear()
    asyncio.run(go(["https://careers.acme.com/jobs/1"]))
    assert [list(r)[0] for r in fake.requests] == ["url_to_scrape"]
