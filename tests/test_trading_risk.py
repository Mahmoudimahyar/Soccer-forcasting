from datetime import datetime, timezone

from wcdrawlab.trading.models import MarketQuote, TradeIntent
from wcdrawlab.trading.risk import PortfolioRiskState, RiskGate, TradingPolicy


def _intent() -> TradeIntent:
    now = datetime.now(timezone.utc)
    return TradeIntent(
        market_ticker="TEST-MKT",
        book_side="bid",
        limit_price_cents=45,
        contracts=2,
        model_probability=0.56,
        model_probability_lower=0.53,
        market_probability=0.45,
        prediction_created_at_utc=now,
        market_observed_at_utc=now,
        model_version="approved-v1",
        rationale="test",
        event_key="test-event",
    )


def test_risk_gate_approves_valid_fresh_intent():
    now = datetime.now(timezone.utc)
    quote = MarketQuote("TEST-MKT", yes_bid_cents=44, yes_ask_cents=46, observed_at_utc=now)
    state = PortfolioRiskState(approved_model_versions=frozenset({"approved-v1"}))
    decision = RiskGate(TradingPolicy()).evaluate(_intent(), quote, state, now=now, confidence_score=0.7)
    assert decision.approved


def test_risk_gate_rejects_unapproved_model():
    now = datetime.now(timezone.utc)
    quote = MarketQuote("TEST-MKT", yes_bid_cents=44, yes_ask_cents=46, observed_at_utc=now)
    decision = RiskGate(TradingPolicy()).evaluate(_intent(), quote, PortfolioRiskState(), now=now)
    assert not decision.approved
    assert "model version is not approved for runtime" in decision.reasons
