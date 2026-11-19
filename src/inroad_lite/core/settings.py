from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    olostep_api_key: str
    olostep_base_url: str = "https://api.olostep.com/v1"
    olostep_timeout_seconds: float = 60.0
    cache_dir: Path = Path(".cache")


def load_settings() -> Settings:
    """Environment first, then a .env file in the working directory."""
    load_dotenv()
    return Settings(
        olostep_api_key=os.getenv("OLOSTEP_API_KEY", "").strip(),
        olostep_base_url=os.getenv("OLOSTEP_BASE_URL", "https://api.olostep.com/v1").strip(),
        olostep_timeout_seconds=float(os.getenv("OLOSTEP_TIMEOUT_SECONDS", "60")),
        cache_dir=Path(os.getenv("INROAD_LITE_CACHE_DIR", ".cache")),
    )
