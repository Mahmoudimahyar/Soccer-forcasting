from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
import uuid


@dataclass(frozen=True)
class MarketQuote:
    market_ticker: str
    yes_bid_cents: int | None
    yes_ask_cents: int | None
    observed_at_utc: datetime
    status: str = "open"
    volume: int | None = None

    @property
    def spread_cents(self) -> int | None:
        if self.yes_bid_cents is None or self.yes_ask_cents is None:
            return None
        return max(0, self.yes_ask_cents - self.yes_bid_cents)


@dataclass(frozen=True)
class TradeIntent:
    """An explicit order instruction after a human-created market mapping.

    `book_side` is intentionally explicit because Kalshi's V2 order endpoint uses a
    single bid/ask book. The model must never infer this mapping from a team name.
    """

    market_ticker: str
    book_side: Literal["bid", "ask"]
    limit_price_cents: int
    contracts: int
    model_probability: float
    model_probability_lower: float
    market_probability: float
    prediction_created_at_utc: datetime
    market_observed_at_utc: datetime
    model_version: str
    rationale: str
    event_key: str
    client_order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # Governance: the registry model id that produced this prediction. When set, the risk gate
    # requires it to be the approved runtime model (shadow models are rejected). None = legacy
    # intent (falls back to the model_version approval check only).
    model_id: str | None = None

    @property
    def edge_after_uncertainty(self) -> float:
        return self.model_probability_lower - self.market_probability

    @property
    def max_cost_cents(self) -> int:
        return int(self.limit_price_cents * self.contracts)


@dataclass(frozen=True)
class TradeDecision:
    approved: bool
    reason: str
    intent: TradeIntent
    evaluated_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
