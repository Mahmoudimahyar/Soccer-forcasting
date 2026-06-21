from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml

from .kalshi import KalshiClient
from .models import MarketQuote, TradeIntent
from .risk import PortfolioRiskState, RiskDecision, RiskGate, TradingPolicy


def policy_from_yaml(path: str | Path) -> TradingPolicy:
    raw = yaml.safe_load(Path(path).read_text())
    risk = raw.get("risk", {})
    return TradingPolicy(
        mode=raw.get("mode", "paper"),
        require_human_confirmation=bool(raw.get("require_human_confirmation", True)),
        allow_unattended_live=bool(raw.get("allow_unattended_live", False)),
        **risk,
    )


def intent_from_json(path: str | Path) -> TradeIntent:
    raw = json.loads(Path(path).read_text())
    for key in ["prediction_created_at_utc", "market_observed_at_utc"]:
        raw[key] = datetime.fromisoformat(raw[key].replace("Z", "+00:00"))
    return TradeIntent(**raw)


def quote_from_json(path: str | Path) -> MarketQuote:
    raw = json.loads(Path(path).read_text())
    raw["observed_at_utc"] = datetime.fromisoformat(raw["observed_at_utc"].replace("Z", "+00:00"))
    return MarketQuote(**raw)


def state_from_json(path: str | Path | None) -> PortfolioRiskState:
    if not path:
        return PortfolioRiskState()
    raw = json.loads(Path(path).read_text())
    raw["approved_model_versions"] = frozenset(raw.get("approved_model_versions", []))
    return PortfolioRiskState(**raw)


def evaluate_intent(intent: TradeIntent, quote: MarketQuote, state: PortfolioRiskState, policy: TradingPolicy, confidence_score: float | None = None) -> RiskDecision:
    return RiskGate(policy).evaluate(intent, quote, state, now=datetime.now(timezone.utc), confidence_score=confidence_score)


def submit_if_approved(
    intent: TradeIntent,
    quote: MarketQuote,
    state: PortfolioRiskState,
    policy: TradingPolicy,
    confidence_score: float | None = None,
    require_live: bool = False,
) -> dict[str, Any]:
    decision = evaluate_intent(intent, quote, state, policy, confidence_score)
    if not decision.approved:
        return {"submitted": False, "approved": False, "reasons": list(decision.reasons)}
    if policy.mode == "paper":
        return {"submitted": False, "approved": True, "mode": "paper", "intent": intent.__dict__}
    if policy.mode not in {"demo", "live"}:
        raise ValueError(f"Unsupported trading mode: {policy.mode}")
    if policy.mode == "live" and policy.require_human_confirmation and not require_live:
        return {"submitted": False, "approved": False, "reasons": ["live policy requires explicit --require-live confirmation"]}
    client = KalshiClient()
    response = client.submit_v2_limit_order(intent, require_live=(policy.mode == "live" and require_live))
    return {"submitted": True, "approved": True, "mode": policy.mode, "response": response}
