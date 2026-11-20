"""A search hit is a lead, not proof. A candidate is kept only once its own
job board has been read and holds an open posting for the searched roles.
The board's own data names the company."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, Protocol

from inroad_lite.core.countries import country_code
from inroad_lite.sourcing.ats.base import BoardAdapter, MalformedListing
from inroad_lite.sourcing.ats.registry import ADAPTERS
from inroad_lite.sourcing.discovery.company_candidates import relevant_title
from inroad_lite.sourcing.discovery.visa_statement import relocation_support, visa_sponsorship
from inroad_lite.sourcing.domain.company_discovery import (
    DEFAULT_DISCOVERY_POLICY,
    Candidate,
    DiscoveryPolicy,
    ProvenCompany,
    RejectReason,
)
from inroad_lite.sourcing.domain.jobs import BoardRef, BoardScan, Job
from inroad_lite.sourcing.net.fetcher import FetchError


class JsonFetcher(Protocol):
    async def get_json(self, url: str, *, allowed_hosts: frozenset[str]) -> Any: ...


class CandidateProver:
    def __init__(
        self, fetcher: JsonFetcher, policy: DiscoveryPolicy = DEFAULT_DISCOVERY_POLICY
    ) -> None:
        self._fetcher = fetcher
        self._policy = policy
        self._scans: dict[BoardRef, asyncio.Future[BoardScan | None]] = {}

    async def prove(
        self, candidate: Candidate, roles: tuple[str, ...]
    ) -> ProvenCompany | RejectReason:
        try:
            return await asyncio.wait_for(
                self._prove(candidate, roles), timeout=self._policy.proof_timeout_seconds
            )
        except TimeoutError:
            return RejectReason.PROOF_TIMEOUT

    async def _prove(
        self, candidate: Candidate, roles: tuple[str, ...]
    ) -> ProvenCompany | RejectReason:
        adapter = ADAPTERS[candidate.ats_provider]
        ref = BoardRef(candidate.ats_provider, candidate.ats_token, candidate.ats_region)
        scan = await self._scan(adapter, ref)
        if scan is None:
            return RejectReason.BOARD_UNREADABLE
        chosen = _choose(candidate, scan, roles, self._policy.max_postings_per_company)
        if isinstance(chosen, RejectReason):
            return chosen
        postings = await asyncio.gather(*(self._with_detail(adapter, ref, job) for job in chosen))
        return ProvenCompany(
            company_name=scan.company_name or candidate.company_name,
            ats_provider=candidate.ats_provider,
            ats_token=candidate.ats_token,
            postings=tuple(postings),
        )

    async def _scan(self, adapter: BoardAdapter, ref: BoardRef) -> BoardScan | None:
        """One read per board per run, shared by every candidate on it."""
        if ref not in self._scans:
            self._scans[ref] = asyncio.ensure_future(self._scan_once(adapter, ref))
        return await asyncio.shield(self._scans[ref])

    async def _scan_once(self, adapter: BoardAdapter, ref: BoardRef) -> BoardScan | None:
        try:
            payload = await self._fetcher.get_json(
                adapter.listing_url(ref), allowed_hosts=adapter.hosts(ref)
            )
            return adapter.parse_listing(payload)
        except (FetchError, MalformedListing):
            return None

    async def _with_detail(self, adapter: BoardAdapter, ref: BoardRef, job: Job) -> Job:
        url = adapter.detail_url(ref, job)
        if url is not None:
            try:
                payload = await self._fetcher.get_json(url, allowed_hosts=adapter.hosts(ref))
                job = adapter.parse_detail(payload, job)
            except FetchError:
                pass  # the posting is proven; only its description is missing
        return with_facts(job)


def with_facts(job: Job) -> Job:
    """What matching needs that the board does not state as a field."""
    text = f"{job.title}\n{job.description or ''}"
    return replace(
        job,
        country=country_code(job.country) if job.country else None,
        visa_sponsorship=visa_sponsorship(text).value,
        relocation_support=relocation_support(text).value,
    )


def _choose(
    candidate: Candidate, scan: BoardScan, roles: tuple[str, ...], limit: int
) -> list[Job] | RejectReason:
    by_id = {job.external_id.lower(): job for job in scan.jobs}
    wanted = [lead.posting_id.lower() for lead in candidate.leads if lead.posting_id]
    if wanted:
        found = list({key: by_id[key] for key in wanted if key in by_id}.values())
        if found:
            return found[:limit]
        # Only a complete listing proves a posting gone; a partial one may
        # simply have missed it.
        return RejectReason.CLOSED if scan.complete else RejectReason.BOARD_UNREADABLE
    # The hit was the board's home page: look for postings for the roles.
    matching = [job for job in scan.jobs if relevant_title(job.title, roles)]
    return matching[:limit] or RejectReason.NO_MATCHING_POSTING
