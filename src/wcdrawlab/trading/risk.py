from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .models import MarketQuote, TradeIntent


@dataclass(frozen=True)
class TradingPolicy:
    mode: str = "paper"  # paper | demo | live
    require_human_confirmation: bool = True
    allow_unattended_live: bool = False
    max_order_cost_cents: int = 500
    max_event_exposure_cents: int = 1500
    max_daily_loss_cents: int = 1000
    max_open_orders: int = 4
    min_edge_after_uncertainty: float = 0.04
    max_market_spread_cents: int = 5
    max_prediction_age_seconds: int = 30
    max_market_age_seconds: int = 10
    min_model_confidence: float = 0.55
    max_contracts_per_order: int = 10
    no_trade_if_stale_data: bool = True
    no_trade_if_market_closed: bool = True
    no_trade_if_model_version_unapproved: bool = True


@dataclass(frozen=True)
class PortfolioRiskState:
    event_exposure_cents: int = 0
    daily_realized_pnl_cents: int = 0
    open_order_count: int = 0
    approved_model_versions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...]


class RiskGate:
    """Deterministic gate that executes before any paper, demo, or live order."""

    def __init__(self, policy: TradingPolicy) -> None:
        self.policy = policy

    def evaluate(
        self,
        intent: TradeIntent,
        quote: MarketQuote,
        state: PortfolioRiskState,
        now: datetime | None = None,
        confidence_score: float | None = None,
    ) -> RiskDecision:
        now = now or datetime.now(timezone.utc)
        failures: list[str] = []
        if intent.limit_price_cents < 1 or intent.limit_price_cents > 99:
            failures.append("limit price must be between 1 and 99 cents")
        if intent.contracts <= 0 or intent.contracts > self.policy.max_contracts_per_order:
            failures.append("contract count exceeds policy")
        if intent.max_cost_cents > self.policy.max_order_cost_cents:
            failures.append("order cost cap exceeded")
        if state.event_exposure_cents + intent.max_cost_cents > self.policy.max_event_exposure_cents:
            failures.append("event exposure cap exceeded")
        if state.daily_realized_pnl_cents <= -abs(self.policy.max_daily_loss_cents):
            failures.append("daily loss stop reached")
        if state.open_order_count >= self.policy.max_open_orders:
            failures.append("open order cap reached")
        if intent.edge_after_uncertainty < self.policy.min_edge_after_uncertainty:
            failures.append("edge after uncertainty is below minimum")
        if confidence_score is not None and confidence_score < self.policy.min_model_confidence:
            failures.append("model confidence below minimum")
        if self.policy.no_trade_if_market_closed and quote.status != "open":
            failures.append("market is not open")
        if self.policy.max_market_spread_cents is not None:
            spread = quote.spread_cents
            if spread is None or spread > self.policy.max_market_spread_cents:
                failures.append("market spread is missing or too wide")
        if self.policy.no_trade_if_stale_data:
            prediction_age = (now - intent.prediction_created_at_utc).total_seconds()
            quote_age = (now - quote.observed_at_utc).total_seconds()
            if prediction_age > self.policy.max_prediction_age_seconds:
                failures.append("prediction is stale")
            if quote_age > self.policy.max_market_age_seconds:
                failures.append("market quote is stale")
        if self.policy.no_trade_if_model_version_unapproved and intent.model_version not in state.approved_model_versions:
            failures.append("model version is not approved for runtime")
        return RiskDecision(approved=not failures, reasons=tuple(failures) if failures else ("approved",))
