"""Find companies hiring for your roles, using Olostep search and public job
boards. The front door: plays inroad-web's part and talks only to api."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from inroad_lite.api.routers import health, match
from inroad_lite.api.schemas.errors import ApiError
from inroad_lite.api.schemas.match import CompanyResult, MatchReport, RoleResult
from inroad_lite.api.schemas.profile import Profile


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="inroad-lite", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="run one search to confirm the Olostep key works")
    search = commands.add_parser("search", help="find companies hiring for a profile")
    search.add_argument("profile", type=Path, help="path to a profile YAML file")
    search.add_argument("--fresh", action="store_true", help="ask Olostep again, skip the cache")
    search.add_argument(
        "--relaxed", action="store_true", help="do not check location or level, only the role"
    )
    search.add_argument(
        "--about",
        type=int,
        default=3,
        metavar="N",
        help="describe the top N companies from their homepage (Olostep scrape; 0 to skip)",
    )
    search.add_argument("--json", type=Path, help="also write the result to this file")
    args = parser.parse_args(argv)

    if args.command == "check":
        return asyncio.run(_check())
    return asyncio.run(_search(args))


async def _check() -> int:
    result = await health.check_olostep()
    if not result.ok:
        print(f"Olostep check failed: {result.error}")
        if result.error and "not set" in result.error:
            print("Copy .env.example to .env and add your OLOSTEP_API_KEY.")
        return 1
    print(f"Olostep key works: {result.results} results, {result.credits} credits used.")
    return 0


async def _search(args: argparse.Namespace) -> int:
    path: Path = args.profile
    try:
        profile = Profile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        print(f"Could not read the profile {path}:\n{exc}")
        return 2
    try:
        report = await match.find_companies(
            profile, fresh=args.fresh, relaxed=args.relaxed, about=args.about
        )
    except ApiError as exc:
        print(f"Search failed ({exc.code}): {exc.message}")
        return 1
    _print(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
        print(f"Saved to {args.json}")
    return 0 if report.companies or not report.failed_searches else 1


def _print(report: MatchReport) -> None:
    print(f"Searched {len(report.searches)} queries.")
    print(
        f"{report.results_seen} results -> {report.boards_read} job boards read -> "
        + (
            "1 company that fits you"
            if report.companies_fitting == 1
            else f"{report.companies_fitting} companies that fit you"
        )
        + (
            f", best {len(report.companies)} shown"
            if len(report.companies) < report.companies_fitting
            else ""
        )
        + (" (relaxed: location and level not checked)" if report.relaxed else "")
        + "\n"
    )
    for index, company in enumerate(report.companies, start=1):
        _print_company(index, company)
    if report.left_out:
        print("Left out:")
        for reason, count in report.left_out.items():
            print(f"  {count:>3}  {reason}")
    if report.failed_searches:
        print(f"\n{len(report.failed_searches)} searches did not answer in time.")
    spend = report.olostep
    print(
        f"\nOlostep: {spend.calls} calls, {spend.credits} credits, "
        f"{spend.answered_from_cache} answered from cache."
    )


def _print_company(index: int, company: CompanyResult) -> None:
    print(f"{index:>2}. {company.name}   {company.score} ({company.band})   [{company.job_board}]")
    about = "  ".join(part for part in (company.website, company.about) if part)
    if about:
        print(f"    {about}")
    _print_role(company.best_role)
    if company.other_roles:
        more = len(company.other_roles)
        titles = ", ".join(role.title for role in company.other_roles)
        print(f"    + {more} more role{'s' if more > 1 else ''} that fit: {titles}")
    print()


def _print_role(role: RoleResult) -> None:
    print(f"    {role.title}   {role.score}")
    for part in role.reasons:
        print(f"      {part.name:<9}{part.detail}")
    print(f"      {role.url}")


if __name__ == "__main__":
    raise SystemExit(main())
