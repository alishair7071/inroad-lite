from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any) -> None: ...


def cache_key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


class FileCache:
    """One JSON file per key, ignored once older than `ttl_seconds`."""

    def __init__(self, directory: Path, *, ttl_seconds: float) -> None:
        self._directory = directory
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        path = self._directory / f"{key}.json"
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if time.time() - stored.get("saved_at", 0) > self._ttl:
            return None
        return stored.get("value")

    def set(self, key: str, value: Any) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        payload = {"saved_at": time.time(), "value": value}
        (self._directory / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")


class NoCache:
    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any) -> None:
        return None
