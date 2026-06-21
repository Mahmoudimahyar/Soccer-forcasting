from __future__ import annotations

import os
from typing import Any

import requests

from .base import ProviderError, SourceRecord


class APIFootballClient:
    """Minimal read-only API-Football adapter.

    The provider's endpoint availability can vary by subscription/season. This adapter
    deliberately surfaces response failures instead of silently substituting data.
    """

    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str | None = None, timeout: float = 20.0) -> None:
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise ProviderError("API_FOOTBALL_KEY is required for APIFootballClient.")

    def _get(self, path: str, params: dict[str, Any] | None = None) -> SourceRecord:
        url = f"{self.BASE_URL}{path}"
        resp = requests.get(url, params=params or {}, headers={"x-apisports-key": self.api_key}, timeout=self.timeout)
        if resp.status_code >= 400:
            raise ProviderError(f"API-Football {resp.status_code}: {resp.text[:500]}")
        payload = resp.json()
        if isinstance(payload, dict) and payload.get("errors"):
            raise ProviderError(f"API-Football returned errors: {payload['errors']}")
        return SourceRecord.create("api_football", path, payload, source_url=resp.url)

    def fixtures(self, league: int, season: int, status: str | None = None) -> SourceRecord:
        params: dict[str, Any] = {"league": league, "season": season}
        if status:
            params["status"] = status
        return self._get("/fixtures", params)

    def fixture_events(self, fixture_id: int) -> SourceRecord:
        return self._get("/fixtures/events", {"fixture": fixture_id})

    def fixture_lineups(self, fixture_id: int) -> SourceRecord:
        return self._get("/fixtures/lineups", {"fixture": fixture_id})

    def fixture_statistics(self, fixture_id: int) -> SourceRecord:
        return self._get("/fixtures/statistics", {"fixture": fixture_id})

    def standings(self, league: int, season: int) -> SourceRecord:
        return self._get("/standings", {"league": league, "season": season})
