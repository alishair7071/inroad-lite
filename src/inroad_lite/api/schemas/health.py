from __future__ import annotations

from pydantic import BaseModel


class OlostepHealth(BaseModel):
    ok: bool
    results: int = 0
    credits: int = 0
    error: str | None = None
