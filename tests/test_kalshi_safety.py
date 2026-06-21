import pytest

from wcdrawlab.trading.kalshi import KalshiClient, KalshiConfig, LiveTradingDisabled


def test_production_execution_is_not_armed_by_default():
    client = KalshiClient(KalshiConfig(environment="production", enable_live_trading=False))
    with pytest.raises(LiveTradingDisabled):
        client._assert_execution_armed(require_live=True)
