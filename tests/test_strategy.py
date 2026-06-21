from datetime import datetime, timezone
from wcdrawlab.trading.models import MarketQuote
from wcdrawlab.trading.strategy import BinaryPosition, StrategyConfig, target_yes_position


def test_target_position_buys_only_on_lower_bound_edge():
    quote = MarketQuote("MKT", 54, 56, datetime.now(timezone.utc))
    position = BinaryPosition("MKT", 0, 0)
    decision = target_yes_position(0.65, quote, position, StrategyConfig(min_edge=0.04, max_contracts=5))
    assert decision.action == "buy"
    assert decision.delta_contracts > 0


def test_target_position_holds_without_edge():
    quote = MarketQuote("MKT", 54, 56, datetime.now(timezone.utc))
    decision = target_yes_position(0.57, quote, BinaryPosition("MKT", 0, 0))
    assert decision.action == "hold"
