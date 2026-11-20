"""The file Vercel runs: the website from src/inroad_lite/web/server.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from inroad_lite.web.server import app  # noqa: E402

__all__ = ["app"]
