"""Ashby's public Job Posting API
(https://developers.ashbyhq.com/docs/public-job-posting-api).

  GET https://api.ashbyhq.com/posting-api/job-board/{job_board_name}

One call returns every posting with its full description (several MB for a
large company)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from inroad_lite.sourcing.ats.base import MalformedListing
from inroad_lite.sourcing.ats.normalize import places, text, workplace
from inroad_lite.sourcing.domain.jobs import BoardRef, BoardScan, Job

_API_HOST = "api.ashbyhq.com"


class Ashby:
    provider = "ashby"

    def hosts(self, ref: BoardRef) -> frozenset[str]:
        return frozenset({_API_HOST})

    def listing_url(self, ref: BoardRef) -> str:
        return f"https://{_API_HOST}/posting-api/job-board/{quote(ref.token, safe='')}"

    def parse_listing(self, payload: Any) -> BoardScan:
        entries = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise MalformedListing("no jobs list")
        jobs = tuple(job for job in (_job(entry) for entry in entries) if job is not None)
        return BoardScan(jobs=jobs, complete=True)

    def detail_url(self, ref: BoardRef, job: Job) -> str | None:
        return None

    def parse_detail(self, payload: Any, job: Job) -> Job:
        return job


def _job(entry: Any) -> Job | None:
    # An unlisted posting is reachable by link but not advertised.
    if not isinstance(entry, dict) or not entry.get("id") or entry.get("isListed") is False:
        return None
    title, url = text(entry.get("title"), 200), text(entry.get("jobUrl"), 2048)
    if not title or not url:
        return None
    secondary = entry.get("secondaryLocations")
    extra = [i.get("location") for i in secondary if isinstance(i, dict)] if secondary else []
    kind = workplace(entry.get("workplaceType"))
    if kind is None and entry.get("isRemote") is True:
        kind = "remote"
    address = entry.get("address")
    postal = address.get("postalAddress") if isinstance(address, dict) else None
    return Job(
        external_id=str(entry["id"]).lower(),
        title=title,
        url=url,
        locations=places([entry.get("location"), *extra]),
        workplace=kind,
        country=text(postal.get("addressCountry"), 60) if isinstance(postal, dict) else None,
        description=text(entry.get("descriptionPlain"), 8000),
        posted_at=text(entry.get("publishedAt"), 40),
    )
