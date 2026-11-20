from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from inroad_lite.api.schemas.errors import ApiError
from inroad_lite.api.schemas.match import MatchReport, OlostepSpend
from inroad_lite.web import server

PROFILE = {"roles": ["Backend Engineer"], "skills": ["Python"], "location": "Lahore, Pakistan"}
CODE = {"X-Access-Code": "open-sesame"}


def empty_report(**_: Any) -> MatchReport:
    return MatchReport(
        searches=["q"],
        failed_searches=[],
        results_seen=0,
        boards_read=0,
        companies_fitting=0,
        companies=[],
        left_out={},
        relaxed=False,
        olostep=OlostepSpend(calls=1, credits=5, answered_from_cache=0),
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("INROAD_LITE_ACCESS_CODE", "open-sesame")
    monkeypatch.setattr(server, "limit", server.RunLimit(3))
    calls: list[dict[str, Any]] = []

    async def fake_find(profile: Any, **options: Any) -> MatchReport:
        calls.append({"profile": profile, **options})
        return empty_report()

    monkeypatch.setattr(server.match, "find_companies", fake_find)
    test_client = TestClient(server.app)
    test_client.calls = calls  # type: ignore[attr-defined]
    return test_client


def test_page_loads_with_safety_headers(client: TestClient):
    res = client.get("/")
    assert res.status_code == 200
    assert "<title>inroad-lite</title>" in res.text
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]
    assert res.headers["x-content-type-options"] == "nosniff"


def test_status_says_what_is_set_never_the_values(client: TestClient, monkeypatch):
    monkeypatch.setenv("OLOSTEP_API_KEY", "secret-key")
    body = client.get("/api/status").json()
    assert body == {"olostep_key_set": True, "access_code_set": True}
    assert "secret" not in client.get("/api/status").text


def test_search_runs_with_the_right_code(client: TestClient):
    res = client.post("/api/search", json={"profile": PROFILE, "relaxed": True}, headers=CODE)
    assert res.status_code == 200
    assert res.json()["olostep"]["credits"] == 5
    (call,) = client.calls  # type: ignore[attr-defined]
    assert call["relaxed"] is True
    assert call["profile"].roles == ["Backend Engineer"]


def test_wrong_or_missing_code_is_refused_before_any_search(client: TestClient):
    wrong = client.post("/api/search", json={"profile": PROFILE}, headers={"X-Access-Code": "no"})
    missing = client.post("/api/search", json={"profile": PROFILE})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["code"] == "wrong_code"
    assert client.calls == []  # type: ignore[attr-defined]


def test_no_code_set_means_the_site_does_not_search(client: TestClient, monkeypatch):
    monkeypatch.delenv("INROAD_LITE_ACCESS_CODE")
    res = client.post("/api/search", json={"profile": PROFILE}, headers=CODE)
    assert res.status_code == 503
    assert res.json()["code"] == "not_set_up"


def test_runs_are_limited_per_hour(client: TestClient):
    codes = [
        client.post("/api/search", json={"profile": PROFILE}, headers=CODE).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]


def test_bad_profile_gets_a_plain_message(client: TestClient):
    res = client.post("/api/search", json={"profile": {"roles": []}}, headers=CODE)
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_input"
    assert "roles" in res.json()["message"]


def test_extra_fields_are_refused(client: TestClient):
    res = client.post("/api/search", json={"profile": PROFILE, "fresh": True}, headers=CODE)
    assert res.status_code == 422


def test_research_turns_a_bad_website_into_400(client: TestClient, monkeypatch):
    async def refuse(domain: str, **_: Any) -> Any:
        raise ApiError("invalid_domain", f"{domain!r} is not a public company website")

    monkeypatch.setattr(server.research_router, "research_company", refuse)
    res = client.post("/api/research", json={"website": "localhost:8080"}, headers=CODE)
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_domain"


def test_sourcing_failure_is_a_502_with_its_message(client: TestClient, monkeypatch):
    async def fail(profile: Any, **_: Any) -> MatchReport:
        raise ApiError("olostep_unavailable", "Olostep did not answer.")

    monkeypatch.setattr(server.match, "find_companies", fail)
    res = client.post("/api/search", json={"profile": PROFILE}, headers=CODE)
    assert res.status_code == 502
    assert res.json() == {"code": "olostep_unavailable", "message": "Olostep did not answer."}
