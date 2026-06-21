"""Read-only data-provider adapters.

Adapters never hold trading authority. They may read environment variables at runtime,
but they must never write secrets or alter .env files.
"""

from .api_football import APIFootballClient
from .odds_api import OddsAPIClient
from .open_meteo import OpenMeteoClient

__all__ = ["APIFootballClient", "OddsAPIClient", "OpenMeteoClient"]
