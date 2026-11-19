from __future__ import annotations

from inroad_lite.sourcing.ats.ashby import Ashby
from inroad_lite.sourcing.ats.greenhouse import Greenhouse
from inroad_lite.sourcing.ats.lever import Lever
from inroad_lite.sourcing.domain.jobs import BoardRef
from tests.support.fake_boards import (
    ashby_listing,
    ashby_url,
    greenhouse_listing,
    greenhouse_url,
    lever_listing,
    lever_url,
)


def test_greenhouse_names_the_company_and_knows_when_the_list_is_whole():
    payload = greenhouse_listing(
        "acme", [(11, "Backend Engineer", "Remote, EMEA"), (12, "Designer", "Berlin")], "Acme Inc"
    )
    scan = Greenhouse().parse_listing(payload)
    assert scan.company_name == "Acme Inc" and scan.complete
    assert [(j.external_id, j.workplace) for j in scan.jobs] == [("11", "remote"), ("12", None)]
    assert scan.jobs[0].locations == ("Remote, EMEA",)
    partial = greenhouse_listing("acme", [(11, "Backend Engineer", "Remote")], "Acme", total=40)
    assert not Greenhouse().parse_listing(partial).complete


def test_greenhouse_reads_the_description_from_the_posting_and_unescapes_it():
    ref = BoardRef("greenhouse", "acme")
    adapter = Greenhouse()
    assert adapter.listing_url(ref) == greenhouse_url("acme")
    (job,) = adapter.parse_listing(greenhouse_listing("acme", [(11, "Backend", "x")], "A")).jobs
    assert adapter.detail_url(ref, job) == greenhouse_url("acme", "11")
    content = (
        "&lt;p&gt;Build APIs in Python.&lt;/p&gt;"
        "&lt;ul&gt;&lt;li&gt;Visa &amp;amp; relocation&lt;/li&gt;"
    )
    detailed = adapter.parse_detail({"content": content}, job)
    assert detailed.description == "Build APIs in Python.\nVisa & relocation"


def test_lever_uses_its_eu_host_and_keeps_requirements_in_the_description():
    ref = BoardRef("lever", "acme", region="eu")
    adapter = Lever()
    assert adapter.listing_url(ref) == lever_url("acme", eu=True)
    assert adapter.hosts(ref) == frozenset({"api.eu.lever.co"})
    scan = adapter.parse_listing(lever_listing("acme", [("a1", "Backend Engineer", "hybrid")]))
    (job,) = scan.jobs
    assert scan.complete and scan.company_name is None
    assert (job.workplace, job.country, job.locations) == ("hybrid", "US", ("New York, NY",))
    assert "Python" in (job.description or "") and "3+ years" in (job.description or "")


def test_ashby_skips_unlisted_postings_and_reads_remote_and_country():
    payload = ashby_listing("acme", [("ABC-1", "Backend Engineer"), ("abc-2", "Hidden")])
    payload["jobs"][1]["isListed"] = False
    payload["jobs"][0]["workplaceType"] = None
    assert Ashby().listing_url(BoardRef("ashby", "acme")) == ashby_url("acme")
    (job,) = Ashby().parse_listing(payload).jobs
    assert (job.external_id, job.workplace, job.country) == ("abc-1", "remote", "Germany")
