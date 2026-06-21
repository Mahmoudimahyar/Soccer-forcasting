from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import floor
from typing import Literal

from .models import MarketQuote, TradeIntent


@dataclass(frozen=True)
class BinaryPosition:
    market_ticker: str
    yes_contracts: int
    average_entry_cents: float


@dataclass(frozen=True)
class StrategyConfig:
    """Conservative target-position policy for a binary market.

    The input probability must be lower confidence bound for entries and upper/point
    estimate for reductions. This function is intentionally simple and can be replaced
    only after event-time calibration evidence exists.
    """

    max_contracts: int = 10
    risk_budget_cents: int = 300
    min_edge: float = 0.04
    exit_buffer: float = 0.02
    fee_buffer: float = 0.01


@dataclass(frozen=True)
class PositionDecision:
    action: Literal["buy", "reduce", "hold"]
    target_yes_contracts: int
    delta_contracts: int
    model_edge: float
    reason: str


def expected_value_per_yes_contract(prob_yes: float, ask_cents: int) -> float:
    """Expected USD payout minus cost per YES contract, expressed in cents."""
    return 100.0 * prob_yes - float(ask_cents)


def contract_variance_cents2(prob_yes: float, price_cents: int) -> float:
    ev = expected_value_per_yes_contract(prob_yes, price_cents)
    yes_pnl = 100.0 - price_cents
    no_pnl = -float(price_cents)
    return prob_yes * (yes_pnl - ev) ** 2 + (1.0 - prob_yes) * (no_pnl - ev) ** 2


def target_yes_position(
    p_yes_lower: float,
    quote: MarketQuote,
    position: BinaryPosition,
    config: StrategyConfig | None = None,
) -> PositionDecision:
    """Return a desired YES position from a conservative edge/variance budget.

    The function does not submit an order and does not infer market mapping. It is a
    deterministic decision primitive for paper/demo/live replay once a reviewed mapping
    specifies how YES exposure is represented on the Kalshi book.
    """
    cfg = config or StrategyConfig()
    if quote.yes_ask_cents is None or quote.yes_bid_cents is None:
        return PositionDecision("hold", position.yes_contracts, 0, 0.0, "missing two-sided quote")
    ask_p = quote.yes_ask_cents / 100.0
    bid_p = quote.yes_bid_cents / 100.0
    entry_edge = p_yes_lower - ask_p - cfg.fee_buffer
    if entry_edge >= cfg.min_edge:
        variance = max(1.0, contract_variance_cents2(p_yes_lower, quote.yes_ask_cents))
        # Inverse-variance allocation, intentionally capped. This is not full Kelly.
        target = min(cfg.max_contracts, max(1, floor(cfg.risk_budget_cents**2 / variance)))
        delta = target - position.yes_contracts
        if delta > 0:
            return PositionDecision("buy", target, delta, entry_edge, "lower-bound edge clears entry threshold")

    # Reduce existing YES exposure when even the point estimate no longer supports it.
    # A caller should supply its current point estimate as p_yes_lower only when running
    # an exit policy explicitly; this conservative function otherwise avoids forced exits.
    exit_edge = p_yes_lower - bid_p - cfg.fee_buffer
    if position.yes_contracts > 0 and exit_edge < -cfg.exit_buffer:
        return PositionDecision("reduce", 0, -position.yes_contracts, exit_edge, "model no longer supports existing YES exposure")
    return PositionDecision("hold", position.yes_contracts, 0, entry_edge, "no uncertainty-adjusted edge")


def intent_from_position_decision(
    decision: PositionDecision,
    quote: MarketQuote,
    market_ticker: str,
    model_probability: float,
    model_probability_lower: float,
    model_version: str,
    event_key: str,
    book_side_for_buy: str,
    book_side_for_reduce: str,
) -> TradeIntent | None:
    if decision.action == "hold" or decision.delta_contracts == 0:
        return None
    now = datetime.now(timezone.utc)
    if decision.action == "buy":
        if quote.yes_ask_cents is None:
            return None
        return TradeIntent(
            market_ticker=market_ticker,
            book_side=book_side_for_buy,  # supplied by approved mapping
            limit_price_cents=quote.yes_ask_cents,
            contracts=decision.delta_contracts,
            model_probability=model_probability,
            model_probability_lower=model_probability_lower,
            market_probability=quote.yes_ask_cents / 100.0,
            prediction_created_at_utc=now,
            market_observed_at_utc=quote.observed_at_utc,
            model_version=model_version,
            rationale=decision.reason,
            event_key=event_key,
        )
    if quote.yes_bid_cents is None:
        return None
    return TradeIntent(
        market_ticker=market_ticker,
        book_side=book_side_for_reduce,
        limit_price_cents=quote.yes_bid_cents,
        contracts=abs(decision.delta_contracts),
        model_probability=model_probability,
        model_probability_lower=model_probability_lower,
        market_probability=quote.yes_bid_cents / 100.0,
        prediction_created_at_utc=now,
        market_observed_at_utc=quote.observed_at_utc,
        model_version=model_version,
        rationale=decision.reason,
        event_key=event_key,
    )
