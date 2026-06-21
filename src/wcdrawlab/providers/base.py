from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class ProviderError(RuntimeError):
    """Raised when an external provider cannot return a trustworthy response."""


@dataclass(frozen=True)
class SourceRecord:
    provider: str
    endpoint: str
    retrieved_at_utc: str
    payload: dict[str, Any]
    source_url: str | None = None

    @classmethod
    def create(cls, provider: str, endpoint: str, payload: dict[str, Any], source_url: str | None = None) -> "SourceRecord":
        return cls(
            provider=provider,
            endpoint=endpoint,
            retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
            payload=payload,
            source_url=source_url,
        )


@dataclass(frozen=True)
class Freshness:
    observed_at_utc: datetime
    max_age_seconds: float

    def is_fresh(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return (now - self.observed_at_utc).total_seconds() <= self.max_age_seconds
