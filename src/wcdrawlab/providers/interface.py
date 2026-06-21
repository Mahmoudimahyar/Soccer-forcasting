"""Provider interface + quota guard for live match data.

Wraps the concrete API-Football adapter behind a single `MatchDataProvider` interface so the rest of
the system never calls a provider directly, and every call is metered against a hard daily quota
(free tier = 100/day). No high-frequency polling is implemented here; this is the interface +
budget. Scheduling decisions live in `schedule.py`.

No secrets are stored or logged. The adapter reads the key from the environment internally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class QuotaExceeded(RuntimeError):
    """Raised when a fetch would exceed the daily request budget (fail closed)."""


@dataclass
class QuotaBudget:
    daily_limit: int = 100
    used: int = 0
    reserve: int = 0  # keep some headroom for higher-priority fetches

    def remaining(self) -> int:
        return max(0, self.daily_limit - self.used - self.reserve)

    def can(self, n: int = 1) -> bool:
        return n <= self.remaining()

    def consume(self, n: int = 1) -> None:
        if not self.can(n):
            raise QuotaExceeded(f"daily quota exhausted: used={self.used} limit={self.daily_limit} need={n}")
        self.used += n


@runtime_checkable
class MatchDataProvider(Protocol):
    """The only surface the system uses for live match data."""
    def fixtures(self, league: int, season: int) -> dict: ...
    def lineups(self, fixture_id: int) -> dict: ...
    def events(self, fixture_id: int) -> dict: ...
    def statistics(self, fixture_id: int) -> dict: ...
    def standings(self, league: int, season: int) -> dict: ...


@dataclass
class APIFootballProvider:
    """API-Football behind the interface, metered by QuotaBudget. Each call consumes one unit and
    fails closed when the budget is gone. Construct the client lazily so importing this module never
    touches the network or credentials."""
    budget: QuotaBudget = field(default_factory=QuotaBudget)
    _client: object | None = None

    def _c(self):
        if self._client is None:
            from wcdrawlab.providers.api_football import APIFootballClient
            self._client = APIFootballClient()
        return self._client

    def _metered(self, fn, *args):
        self.budget.consume(1)
        rec = fn(*args)
        return getattr(rec, "payload", rec)

    def fixtures(self, league: int, season: int) -> dict:
        return self._metered(self._c().fixtures, league, season)

    def lineups(self, fixture_id: int) -> dict:
        return self._metered(self._c().fixture_lineups, fixture_id)

    def events(self, fixture_id: int) -> dict:
        return self._metered(self._c().fixture_events, fixture_id)

    def statistics(self, fixture_id: int) -> dict:
        return self._metered(self._c().fixture_statistics, fixture_id)

    def standings(self, league: int, season: int) -> dict:
        return self._metered(self._c().standings, league, season)
