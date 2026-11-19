from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkPreference = Literal["remote", "onsite", "hybrid", "relocation"]


def _remote_only() -> list[WorkPreference]:
    return ["remote"]


class Profile(BaseModel):
    """What the search needs to know about the person. Nothing else."""

    model_config = ConfigDict(extra="forbid")

    roles: list[str] = Field(min_length=1, max_length=4)
    skills: list[str] = Field(default_factory=list)
    # "City, Country" or just a country.
    location: str | None = None
    work_preference: list[WorkPreference] = Field(default_factory=_remote_only)
    # Regions a relocation search asks for, e.g. ["Europe", "Canada"].
    relocation_places: list[str] = Field(default_factory=list, max_length=4)
    years_experience: float | None = Field(default=None, ge=0, le=70)

    @property
    def city(self) -> str | None:
        parts = self._place_parts()
        return parts[0] if parts else None

    @property
    def country(self) -> str | None:
        parts = self._place_parts()
        return parts[-1] if len(parts) > 1 else None

    def _place_parts(self) -> list[str]:
        return [part.strip() for part in (self.location or "").split(",") if part.strip()]
