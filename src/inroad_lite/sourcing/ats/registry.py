from __future__ import annotations

from inroad_lite.sourcing.ats.ashby import Ashby
from inroad_lite.sourcing.ats.base import BoardAdapter
from inroad_lite.sourcing.ats.greenhouse import Greenhouse
from inroad_lite.sourcing.ats.lever import Lever

ADAPTERS: dict[str, BoardAdapter] = {
    adapter.provider: adapter for adapter in (Greenhouse(), Lever(), Ashby())
}
