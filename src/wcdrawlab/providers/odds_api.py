from __future__ import annotations

import os
from typing import Any

import requests

from .base import ProviderError, SourceRecord


class OddsAPIClient:
    """Read-only adapter for The Odds API v4.

    Store raw snapshots before normalizing so every prediction can be reproduced.
    """

    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str | None = None, timeout: float = 20.0) -> None:
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise ProviderError("ODDS_API_KEY is required for OddsAPIClient.")

    def odds(
        self,
        sport_key: str,
        regions: str = "us",
        markets: str = "h2h,totals,spreads",
        odds_format: str = "decimal",
        date_format: str = "iso",
    ) -> SourceRecord:
        path = f"/sports/{sport_key}/odds"
        params: dict[str, Any] = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        }
        resp = requests.get(f"{self.BASE_URL}{path}", params=params, timeout=self.timeout)
        if resp.status_code >= 400:
            raise ProviderError(f"The Odds API {resp.status_code}: {resp.text[:500]}")
        return SourceRecord.create("the_odds_api", path, {"data": resp.json(), "headers": dict(resp.headers)}, source_url=resp.url)
