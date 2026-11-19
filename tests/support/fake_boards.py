"""Scripted public job boards: a URL -> payload map in place of the network,
and builders for each board's real response shape."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

from inroad_lite.sourcing.net.fetcher import FetchError


def greenhouse_url(token: str, job_id: str | None = None) -> str:
    base = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    return f"{base}/{job_id}" if job_id else base


def lever_url(token: str, *, eu: bool = False) -> str:
    host = "api.eu.lever.co" if eu else "api.lever.co"
    return f"https://{host}/v0/postings/{token}?mode=json"


def ashby_url(token: str) -> str:
    return f"https://api.ashbyhq.com/posting-api/job-board/{token}"


def greenhouse_listing(
    token: str, jobs: list[tuple[int, str, str]], company: str, *, total: int | None = None
) -> dict[str, Any]:
    """jobs: (id, title, location)."""
    return {
        "jobs": [
            {
                "id": job_id,
                "title": title,
                "location": {"name": where},
                "absolute_url": f"https://job-boards.greenhouse.io/{token}/jobs/{job_id}",
                "company_name": company,
                "first_published": "2026-11-01T10:00:00-05:00",
            }
            for job_id, title, where in jobs
        ],
        "meta": {"total": len(jobs) if total is None else total},
    }


def lever_listing(token: str, jobs: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    """jobs: (id, title, workplaceType)."""
    return [
        {
            "id": job_id,
            "text": title,
            "hostedUrl": f"https://jobs.lever.co/{token}/{job_id}",
            "workplaceType": kind,
            "country": "US",
            "categories": {"location": "New York, NY", "allLocations": ["New York, NY"]},
            "descriptionPlain": f"{title} working with Python and Docker.",
            "lists": [{"text": "Requirements", "content": "<li>3+ years</li>"}],
        }
        for job_id, title, kind in jobs
    ]


def ashby_listing(token: str, jobs: list[tuple[str, str]]) -> dict[str, Any]:
    """jobs: (id, title)."""
    return {
        "apiVersion": "1",
        "jobs": [
            {
                "id": job_id,
                "title": title,
                "location": "Remote - Europe",
                "workplaceType": "Remote",
                "isRemote": True,
                "isListed": True,
                "jobUrl": f"https://jobs.ashbyhq.com/{token}/{job_id}",
                "descriptionPlain": f"{title}. Visa sponsorship available.",
                "address": {"postalAddress": {"addressCountry": "Germany"}},
            }
            for job_id, title in jobs
        ],
    }


class FakeBoards:
    def __init__(self, payloads: dict[str, Any], *, delay: float = 0.0) -> None:
        self.payloads = payloads
        self.requests: list[str] = []
        self._delay = delay

    async def __aenter__(self) -> FakeBoards:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get_json(self, url: str, *, allowed_hosts: frozenset[str]) -> Any:
        assert urlsplit(url).hostname in allowed_hosts, url
        self.requests.append(url)
        if self._delay:
            await asyncio.sleep(self._delay)
        if url not in self.payloads:
            raise FetchError("http 404")
        return self.payloads[url]
