"""Sourcing's entry point for company discovery. HTTP only in Inroad
(POST /v1/company-discovery); here the same job as a function: take the
contract in, call the service, give the contract back."""

from __future__ import annotations

from inroad_lite.core.settings import load_settings
from inroad_lite.sourcing.api import dependencies
from inroad_lite.sourcing.domain.company_discovery import DiscoveryRequest, ProvenCompany
from inroad_lite.sourcing.domain.olostep import OlostepAuthError
from inroad_lite.sourcing.schemas.company_discovery import (
    CompanyOut,
    DiscoveryRequestIn,
    DiscoveryResponse,
    OlostepUsageOut,
    PostingOut,
    SourcingError,
)
from inroad_lite.sourcing.services.candidate_proof import CandidateProver
from inroad_lite.sourcing.services.company_discovery import discover_companies


async def discover(body: DiscoveryRequestIn) -> DiscoveryResponse:
    settings = load_settings()
    try:
        async with (
            dependencies.make_olostep_client(settings, fresh=body.fresh) as client,
            dependencies.make_board_fetcher() as fetcher,
        ):
            outcome = await discover_companies(_request(body), client, CandidateProver(fetcher))
    except OlostepAuthError as exc:
        raise SourcingError("olostep_auth", str(exc)) from None
    return DiscoveryResponse(
        queries=outcome.queries,
        failed_queries=outcome.failed_queries,
        hits_seen=outcome.hits_seen,
        candidates_found=outcome.candidates_found,
        companies=[_company(company) for company in outcome.companies],
        rejected=dict(outcome.rejected),
        olostep=OlostepUsageOut(**vars(client.usage)),
    )


def _request(body: DiscoveryRequestIn) -> DiscoveryRequest:
    return DiscoveryRequest(
        roles=tuple(body.roles),
        keywords=tuple(body.keywords),
        locations=tuple(body.locations),
        remote=body.remote,
        onsite=body.onsite,
        relocation=body.relocation,
        relocation_places=tuple(body.relocation_places),
    )


def _company(company: ProvenCompany) -> CompanyOut:
    return CompanyOut(
        company_name=company.company_name,
        ats_provider=company.ats_provider,
        ats_token=company.ats_token,
        postings=[
            PostingOut(
                posting_id=job.external_id,
                title=job.title,
                url=job.url,
                locations=list(job.locations),
                workplace=job.workplace,
                country=job.country,
                description=job.description,
                posted_at=job.posted_at,
                visa_sponsorship=job.visa_sponsorship,
                relocation_support=job.relocation_support,
            )
            for job in company.postings
        ],
    )
