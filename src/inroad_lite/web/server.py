"""The website: one page and two JSON endpoints. Like cli.py it plays the
web part and talks only to api's routers and schemas.

Every search spends the owner's Olostep credits, so the endpoints need an
access code (INROAD_LITE_ACCESS_CODE) and are limited per hour. Without a
code set, the site refuses to search rather than run open."""

from __future__ import annotations

import asyncio
import hmac
import os
import time
from collections import deque
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from inroad_lite.api.routers import match
from inroad_lite.api.routers import research as research_router
from inroad_lite.api.schemas.errors import ApiError
from inroad_lite.api.schemas.match import MatchReport
from inroad_lite.api.schemas.profile import Profile
from inroad_lite.api.schemas.research import ResearchReport

load_dotenv()
# On Vercel only /tmp can be written; the cache lives there for as long as
# the server instance does.
if os.getenv("VERCEL") and not os.getenv("INROAD_LITE_CACHE_DIR"):
    os.environ["INROAD_LITE_CACHE_DIR"] = "/tmp/inroad-lite-cache"

PAGE = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class SearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: Profile
    relaxed: bool = False


class ResearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website: str = Field(min_length=3, max_length=200)
    profile: Profile | None = None
    relaxed: bool = False


class RunLimit:
    """At most `per_hour` runs in any hour. Counted per server instance."""

    def __init__(self, per_hour: int) -> None:
        self._per_hour = per_hour
        self._started: deque[float] = deque()

    def take(self) -> bool:
        now = time.monotonic()
        while self._started and now - self._started[0] > 3600:
            self._started.popleft()
        if len(self._started) >= self._per_hour:
            return False
        self._started.append(now)
        return True


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.update(HEADERS)
        return response


app = FastAPI(title="inroad-lite", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SecurityHeaders)
limit = RunLimit(int(os.getenv("INROAD_LITE_RUNS_PER_HOUR", "10")))
# Two at a time is plenty for a demo and keeps one visitor from fanning out.
running = asyncio.Semaphore(2)


@app.exception_handler(RequestValidationError)
async def bad_input(request: Request, exc: RequestValidationError) -> JSONResponse:
    problems = [
        f"{'.'.join(str(p) for p in error['loc'][1:]) or 'input'}: {error['msg']}"
        for error in exc.errors()
    ]
    return JSONResponse(
        {"code": "invalid_input", "message": "; ".join(problems[:5])}, status_code=422
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    code, message = exc.detail if isinstance(exc.detail, tuple) else ("error", str(exc.detail))
    return JSONResponse({"code": code, "message": message}, status_code=exc.status_code)


@app.get("/", response_class=HTMLResponse)
async def page() -> str:
    return PAGE


@app.get("/api/status")
async def status() -> dict[str, bool]:
    """Whether the site is set up; never the values themselves."""
    return {
        "olostep_key_set": bool(os.getenv("OLOSTEP_API_KEY", "").strip()),
        "access_code_set": bool(os.getenv("INROAD_LITE_ACCESS_CODE", "").strip()),
    }


@app.post("/api/search")
async def search(body: SearchIn, x_access_code: Annotated[str, Header()] = "") -> MatchReport:
    _admit(x_access_code)
    async with running:
        try:
            return await match.find_companies(body.profile, relaxed=body.relaxed)
        except ApiError as exc:
            raise HTTPException(502, (exc.code, exc.message)) from None


@app.post("/api/research")
async def research(
    body: ResearchIn, x_access_code: Annotated[str, Header()] = ""
) -> ResearchReport:
    _admit(x_access_code)
    async with running:
        try:
            return await research_router.research_company(
                body.website, profile=body.profile, relaxed=body.relaxed
            )
        except ApiError as exc:
            status_code = 400 if exc.code == "invalid_domain" else 502
            raise HTTPException(status_code, (exc.code, exc.message)) from None


def _admit(given: str) -> None:
    expected = os.getenv("INROAD_LITE_ACCESS_CODE", "").strip()
    if not expected:
        raise HTTPException(503, ("not_set_up", "This site has no access code set yet."))
    if not hmac.compare_digest(given.strip().encode(), expected.encode()):
        raise HTTPException(401, ("wrong_code", "That access code is not right."))
    if not limit.take():
        raise HTTPException(
            429, ("too_many", "The hourly limit of runs is used up. Try again later.")
        )
