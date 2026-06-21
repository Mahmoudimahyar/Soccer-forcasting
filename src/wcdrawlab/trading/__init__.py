"""Guarded execution layer.

This package is intentionally isolated from the research sandbox. It defaults to paper
trading and requires explicit environment-based arming before any production order can
be submitted.
"""

from .models import TradeIntent, MarketQuote, TradeDecision
from .risk import TradingPolicy, RiskGate, RiskDecision
from .kalshi import KalshiClient, KalshiConfig, LiveTradingDisabled
from .strategy import BinaryPosition, StrategyConfig, PositionDecision, target_yes_position

__all__ = [
    "TradeIntent", "MarketQuote", "TradeDecision", "TradingPolicy", "RiskGate", "RiskDecision",
    "KalshiClient", "KalshiConfig", "LiveTradingDisabled",
    "BinaryPosition", "StrategyConfig", "PositionDecision", "target_yes_position",
]
