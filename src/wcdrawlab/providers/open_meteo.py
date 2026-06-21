from __future__ import annotations

from typing import Any

import requests

from .base import ProviderError, SourceRecord


class OpenMeteoClient:
    """Keyless forecast adapter used for venue condition features."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def forecast(self, latitude: float, longitude: float, timezone_name: str = "auto") -> SourceRecord:
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone_name,
            "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m,wind_gusts_10m",
            "forecast_days": 16,
        }
        resp = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
        if resp.status_code >= 400:
            raise ProviderError(f"Open-Meteo {resp.status_code}: {resp.text[:500]}")
        return SourceRecord.create("open_meteo", "/v1/forecast", resp.json(), source_url=resp.url)
