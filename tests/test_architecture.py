"""The boundaries between the parts, held by imports: web talks
only to api; api reaches sourcing only through its contract and one client;
sourcing never knows about api or web; only sourcing's net layer opens a
network connection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src" / "inroad_lite"
SOURCING_CLIENT = ROOT / "api" / "services" / "sourcing_client.py"


def imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def modules(package: str) -> list[Path]:
    return sorted((ROOT / package).rglob("*.py"))


@pytest.mark.parametrize("path", modules("web"), ids=lambda p: p.name)
def test_web_talks_only_to_api_routers_and_schemas(path: Path):
    ours = {name for name in imports(path) if name.startswith("inroad_lite.")}
    assert all(
        name.startswith(("inroad_lite.api.routers", "inroad_lite.api.schemas")) for name in ours
    ), ours


@pytest.mark.parametrize("path", modules("api"), ids=lambda p: p.name)
def test_api_reaches_sourcing_only_through_its_contract_and_client(path: Path):
    for name in imports(path):
        if name.startswith("inroad_lite.web"):
            pytest.fail(f"{path.name} imports web")
        if name.startswith("inroad_lite.sourcing.api"):
            assert path == SOURCING_CLIENT, f"{path.name} calls sourcing directly"
        elif name.startswith("inroad_lite.sourcing"):
            assert name.startswith("inroad_lite.sourcing.schemas"), f"{path.name}: {name}"


@pytest.mark.parametrize("path", modules("sourcing"), ids=lambda p: p.name)
def test_sourcing_knows_nothing_of_api_or_web(path: Path):
    assert not any(
        name.startswith(("inroad_lite.api", "inroad_lite.web")) for name in imports(path)
    )


def test_only_sourcings_net_layer_opens_connections():
    for path in ROOT.rglob("*.py"):
        if "httpx" in imports(path):
            assert path.parent == ROOT / "sourcing" / "net", path
