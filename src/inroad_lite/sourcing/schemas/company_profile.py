"""Sourcing's public contract for a company's "about". Like discovery, no
user data crosses: a company name and its posting links."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from inroad_lite.sourcing.schemas.company_discovery import OlostepUsageOut

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CompanyProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    posting_urls: list[str] = Field(default_factory=list, max_length=10)
    fresh: bool = False


class CompanyProfileOut(BaseModel):
    name: str
    domain: str | None
    summary: str | None
    olostep: OlostepUsageOut
