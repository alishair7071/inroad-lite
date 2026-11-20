"""Stage A of matching: from a request to proven companies. Builds the
queries, runs them through Olostep at the same time, merges the hits by
company board, then reads each board to prove an open posting."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field

from inroad_lite.sourcing.discovery.company_candidates import build_queries, candidate_from_hit
from inroad_lite.sourcing.domain.company_discovery import (
    DEFAULT_DISCOVERY_POLICY,
    Candidate,
    DiscoveryPolicy,
    DiscoveryRequest,
    ProvenCompany,
    RejectReason,
)
from inroad_lite.sourcing.domain.olostep import OlostepAuthError, OlostepError
from inroad_lite.sourcing.net.olostep import OlostepClient
from inroad_lite.sourcing.services.candidate_proof import CandidateProver


@dataclass
class DiscoveryOutcome:
    queries: list[str]
    hits_seen: int
    candidates_found: int = 0
    companies: list[ProvenCompany] = field(default_factory=list)
    rejected: Counter[str] = field(default_factory=Counter)
    failed_queries: list[str] = field(default_factory=list)


async def discover_companies(
    request: DiscoveryRequest,
    client: OlostepClient,
    prover: CandidateProver,
    policy: DiscoveryPolicy = DEFAULT_DISCOVERY_POLICY,
) -> DiscoveryOutcome:
    queries = build_queries(request, limit=policy.max_query_searches)
    results = await asyncio.gather(
        *(client.search(query) for query in queries), return_exceptions=True
    )
    found: dict[tuple[str, str], Candidate] = {}
    outcome = DiscoveryOutcome(queries=queries, hits_seen=0)
    for query, result in zip(queries, results, strict=True):
        if isinstance(result, OlostepAuthError):
            raise result
        if isinstance(result, OlostepError):
            # One slow search must not cost the others.
            outcome.failed_queries.append(query)
            continue
        if isinstance(result, BaseException):
            raise result
        for hit in result[: policy.max_hits_per_query]:
            outcome.hits_seen += 1
            candidate = candidate_from_hit(hit, roles=request.roles)
            if isinstance(candidate, RejectReason):
                outcome.rejected[candidate.value] += 1
            else:
                _merge(found, candidate)
    candidates = list(found.values())[: policy.max_candidates_to_prove]
    outcome.candidates_found = len(candidates)
    proofs = await asyncio.gather(*(prover.prove(c, request.roles) for c in candidates))
    for proof in proofs:
        if isinstance(proof, RejectReason):
            outcome.rejected[proof.value] += 1
        else:
            outcome.companies.append(proof)
    return outcome


def _merge(found: dict[tuple[str, str], Candidate], candidate: Candidate) -> None:
    key = (candidate.ats_provider, candidate.ats_token.lower())
    existing = found.get(key)
    if existing is None:
        found[key] = candidate
        return
    urls = {lead.url for lead in existing.leads}
    existing.leads.extend(lead for lead in candidate.leads if lead.url not in urls)
