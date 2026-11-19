"""Greenhouse's public Job Board API (https://developers.greenhouse.io/job-board.html).

  GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs
  GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{id}

The listing is read without descriptions (with them, one large company is
about 4 MB); the description is read per chosen posting."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from inroad_lite.sourcing.ats.base import MalformedListing
from inroad_lite.sourcing.ats.normalize import html_to_text, places, remote_from_locations, text
from inroad_lite.sourcing.domain.jobs import BoardRef, BoardScan, Job

_API_HOST = "boards-api.greenhouse.io"


class Greenhouse:
    provider = "greenhouse"

    def hosts(self, ref: BoardRef) -> frozenset[str]:
        return frozenset({_API_HOST})

    def listing_url(self, ref: BoardRef) -> str:
        return f"https://{_API_HOST}/v1/boards/{quote(ref.token, safe='')}/jobs"

    def parse_listing(self, payload: Any) -> BoardScan:
        entries = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise MalformedListing("no jobs list")
        jobs = tuple(job for job in (_job(entry) for entry in entries) if job is not None)
        meta = payload.get("meta")
        total = meta.get("total") if isinstance(meta, dict) else None
        company = next(
            (text(e.get("company_name"), 120) for e in entries if isinstance(e, dict)), None
        )
        return BoardScan(jobs=jobs, complete=total == len(entries), company_name=company)

    def detail_url(self, ref: BoardRef, job: Job) -> str | None:
        token = quote(ref.token, safe="")
        return f"https://{_API_HOST}/v1/boards/{token}/jobs/{quote(job.external_id, safe='')}"

    def parse_detail(self, payload: Any, job: Job) -> Job:
        if not isinstance(payload, dict):
            return job
        # content arrives entity-escaped: html_to_text unescapes before parsing.
        return Job(**{**job.__dict__, "description": html_to_text(payload.get("content"))})


def _job(entry: Any) -> Job | None:
    if not isinstance(entry, dict) or entry.get("id") is None:
        return None
    title, url = text(entry.get("title"), 200), text(entry.get("absolute_url"), 2048)
    if not title or not url:
        return None
    location = entry.get("location")
    locations = places([location.get("name") if isinstance(location, dict) else None])
    return Job(
        external_id=str(entry["id"]),
        title=title,
        url=url,
        locations=locations,
        workplace=remote_from_locations(locations),
        posted_at=text(entry.get("first_published"), 40),
    )
