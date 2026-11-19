from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_real_olostep(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    """Whatever .env holds, tests never spend credits: the key is blank (so
    an unfaked client fails at once) and the cache is a fresh folder."""
    monkeypatch.setenv("OLOSTEP_API_KEY", "")
    monkeypatch.setenv("INROAD_LITE_CACHE_DIR", str(tmp_path_factory.mktemp("cache")))
