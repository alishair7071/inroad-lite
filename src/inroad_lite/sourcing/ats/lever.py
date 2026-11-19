"""Lever's public Postings API (https://github.com/lever/postings-api).

  GET https://api.lever.co/v0/postings/{site}?mode=json
  (EU boards: https://api.eu.lever.co/v0/postings/{site}?mode=json)

One call returns every posting with its description."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from inroad_lite.sourcing.ats.base import MalformedListing
from inroad_lite.sourcing.ats.normalize import html_to_text, places, text, workplace
from inroad_lite.sourcing.domain.jobs import BoardRef, BoardScan, Job

_API_HOSTS = {None: "api.lever.co", "eu": "api.eu.lever.co"}


class Lever:
    provider = "lever"

    def hosts(self, ref: BoardRef) -> frozenset[str]:
        return frozenset({_host(ref)})

    def listing_url(self, ref: BoardRef) -> str:
        return f"https://{_host(ref)}/v0/postings/{quote(ref.token, safe='')}?mode=json"

    def parse_listing(self, payload: Any) -> BoardScan:
        if not isinstance(payload, list):
            raise MalformedListing("not a list of postings")
        jobs = tuple(job for job in (_job(entry) for entry in payload) if job is not None)
        # No paging asked for, so the list is the whole board.
        return BoardScan(jobs=jobs, complete=True)

    def detail_url(self, ref: BoardRef, job: Job) -> str | None:
        return None

    def parse_detail(self, payload: Any, job: Job) -> Job:
        return job


def _host(ref: BoardRef) -> str:
    return _API_HOSTS.get(ref.region, _API_HOSTS[None])


def _job(entry: Any) -> Job | None:
    if not isinstance(entry, dict) or not entry.get("id"):
        return None
    title, url = text(entry.get("text"), 200), text(entry.get("hostedUrl"), 2048)
    if not title or not url:
        return None
    raw = entry.get("categories")
    categories: dict[str, Any] = raw if isinstance(raw, dict) else {}
    every = categories.get("allLocations")
    locations = places(every if isinstance(every, list) else [categories.get("location")])
    return Job(
        external_id=str(entry["id"]),
        title=title,
        url=url,
        locations=locations,
        workplace=workplace(entry.get("workplaceType")),
        country=text(entry.get("country"), 60),
        description=_description(entry),
    )


def _description(entry: dict[str, Any]) -> str | None:
    """The opening text plus each requirements list: where skills and visa
    terms are written."""
    raw = entry.get("lists")
    lists: list[Any] = raw if isinstance(raw, list) else []
    parts = [
        text(entry.get("descriptionPlain"), 6000),
        *(html_to_text(item.get("content")) for item in lists if isinstance(item, dict)),
        text(entry.get("additionalPlain"), 2000),
    ]
    joined = "\n".join(part for part in parts if part)
    return joined[:8000] or None
