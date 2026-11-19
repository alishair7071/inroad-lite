"""Inroad's fit rules, on the kind of postings a live run returns."""

from __future__ import annotations

import pytest

from inroad_lite.api.schemas.profile import Profile
from inroad_lite.api.services.match_fit import fit
from inroad_lite.sourcing.schemas.company_discovery import PostingOut

PROFILE = Profile(
    roles=["Backend Engineer", "DevOps Engineer"],
    skills=["Python", "Docker", "AWS", "Kubernetes"],
    location="Lahore, Pakistan",
    work_preference=["remote", "relocation"],
    relocation_places=["Europe", "Canada"],
    years_experience=2,
)


def posting(title: str, *locations: str, **facts: object) -> PostingOut:
    values: dict[str, object] = {
        "posting_id": "1", "title": title, "url": "https://x", "locations": list(locations),
        "workplace": None, "country": None, "description": None, "posted_at": None,
        "visa_sponsorship": "not_stated", "relocation_support": "not_stated",
    }  # fmt: skip
    values.update(facts)
    return PostingOut.model_validate(values)


@pytest.mark.parametrize(
    "locations",
    [("Remote - Worldwide",), ("Remote, APAC",), ("Remote", "Pakistan"), ("Anywhere (Remote)",)],
)
def test_remote_open_to_pakistan_fits(locations):
    verdict = fit(PROFILE, posting("Backend Engineer", *locations, workplace="remote"))
    assert verdict.ok and verdict.reason.startswith("Remote, open to Pakistan")


@pytest.mark.parametrize(
    "locations", [("Remote - United States",), ("Remote, EMEA",), ("Remote",), ("India Remote",)]
)
def test_remote_closed_to_pakistan_or_not_saying_does_not_fit(locations):
    verdict = fit(PROFILE, posting("Backend Engineer", *locations, workplace="remote"))
    assert not verdict.ok and verdict.reason.startswith("location")


def test_relocation_needs_an_offer_in_a_chosen_place():
    berlin = posting("Backend Engineer", "Berlin", visa_sponsorship="offered")
    assert fit(PROFILE, berlin).reason == "Berlin, with visa sponsorship"
    tokyo = posting("Backend Engineer", "Tokyo, Japan", visa_sponsorship="offered")
    assert not fit(PROFILE, tokyo).ok
    no_visa = posting(
        "Backend Engineer", "Berlin",
        visa_sponsorship="not_offered", relocation_support="offered",
    )  # fmt: skip
    assert not fit(PROFILE, no_visa).ok


@pytest.mark.parametrize(
    ("title", "reason"),
    [
        ("Senior Backend Engineer", "senior role"),
        ("Staff Backend Engineer", "staff-level role"),
        ("Rust Engineer", "different stack"),
        ("Sr. GIS Solution Engineer - Commercial", "senior role"),
        ("GIS Solution Engineer", "sales_engineering role"),
        ("Engineering Manager, Backend", "management role"),
        ("Product Designer", "design role"),
    ],
)
def test_level_and_role_rules(title, reason):
    verdict = fit(PROFILE, posting(title, "Remote - Worldwide", workplace="remote"))
    assert (verdict.ok, verdict.reason) == (False, reason)


def test_relaxed_skips_location_and_level_but_not_the_role():
    us = posting("Senior Backend Engineer", "Remote - United States", workplace="remote")
    verdict = fit(PROFILE, us, relaxed=True)
    assert verdict.ok and verdict.reason == "Remote - United States (location not checked)"
    assert not fit(PROFILE, posting("Product Designer", "Remote"), relaxed=True).ok
