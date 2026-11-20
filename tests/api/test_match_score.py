from __future__ import annotations

from datetime import UTC, datetime

from inroad_lite.api.services.match_score import band, score_company, score_role

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def score(title: str, text: str = "", posted_at: str | None = "2026-11-18T00:00:00Z", years=2.0):  # type: ignore[no-untyped-def]
    return score_role(
        targets=["Backend Engineer"],
        skills=["Python", "Docker", "AWS"],
        years=years,
        title=title,
        text=text,
        posted_at=posted_at,
        location="Remote, open to Pakistan",
        now=NOW,
    )


def test_every_point_comes_from_a_part_that_is_shown():
    found = score("Backend Engineer", "We use Python, Docker and AWS.")
    parts = {part.name: (part.detail, part.value) for part in found.parts}
    assert parts["Role"] == ("Matches your target Backend Engineer", 1.0)
    assert parts["Skills"] == ("Names Python, Docker, AWS", 1.0)
    assert parts["Level"] == ("Mid level, fits your 2 years", 1.0)
    assert parts["Posted"] == ("2 days ago", 1.0)
    assert found.score == 35 + 40 + 10 + 15 == 100
    assert found.band == "strong"


def test_a_level_away_from_the_years_worked_loses_points():
    found = score("Senior Backend Engineer", years=2.0)
    level = next(part for part in found.parts if part.name == "Level")
    assert (level.detail, level.value) == ("Senior level, a step from your 2 years", 0.5)


def test_a_skill_listed_twice_counts_once():
    found = score_role(
        targets=["Backend Engineer"], skills=["Python", "python"], years=2.0,
        title="Backend Engineer", text="Python", posted_at=None, location="x", now=NOW,
    )  # fmt: skip
    assert found.matched_skills == ("Python",)


def test_what_cannot_be_checked_counts_as_half():
    found = score("Backend Engineer", "", posted_at=None, years=None)
    assert found.score == round(35 + 40 * 0.5 + 10 * 0.5 + 15 * 0.5)


def test_a_posting_whose_text_was_not_read_has_unknown_not_missing_skills():
    unread = score_role(
        targets=["Backend Engineer"], skills=["Python"], years=2.0, title="Backend Engineer",
        text="Backend Engineer", posted_at=None, location="x", now=NOW, described=False,
    )  # fmt: skip
    skills = next(part for part in unread.parts if part.name == "Skills")
    assert (skills.detail, skills.value) == ("Posting text not read; counted as unknown", None)


def test_skills_must_be_whole_words():
    found = score("Backend Engineer", "Experience with Golang and AWSome tools")
    assert dict((p.name, p.detail) for p in found.parts)["Skills"].startswith("None of yours")


def test_a_company_with_more_fitting_roles_ranks_higher():
    best = score("Backend Engineer", "Python Docker AWS")
    assert score_company(best, 3) > score_company(best, 1)
    assert band(80) == "strong" and band(60) == "good" and band(40) == "possible"
