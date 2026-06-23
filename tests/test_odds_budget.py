"""Tests for the fail-closed Odds API budget/rate guard. No network."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.operations.odds_budget import OddsBudget  # noqa: E402

T0 = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc)


def _clock(holder):
    return lambda: holder["t"]


def test_budget_ceiling_fail_closed(tmp_path):
    h = {"t": T0}
    b = OddsBudget(tmp_path / "b.json", max_credits=3, min_interval_s=0, clock=_clock(h))
    assert b.can_request(1)[0] is True
    b.record_request(3)
    assert b.remaining() == 0
    ok, reason = b.can_request(1)
    assert ok is False and "budget would be exceeded" in reason


def test_rate_limit_fail_closed_and_persists(tmp_path):
    h = {"t": T0}
    b = OddsBudget(tmp_path / "b.json", max_credits=500, min_interval_s=600, clock=_clock(h))
    assert b.can_request(1)[0] is True
    b.record_request(1)
    ok, reason = b.can_request(1)            # immediately after -> blocked
    assert ok is False and "rate limit" in reason
    h["t"] = T0 + timedelta(seconds=601)     # after interval -> allowed
    assert b.can_request(1)[0] is True
    # persistence across instances
    b2 = OddsBudget(tmp_path / "b.json", max_credits=500, min_interval_s=600, clock=_clock(h))
    assert b2.credits_used == 1 and b2.summary()["requests"] == 1


def test_projected_credits_validated(tmp_path):
    b = OddsBudget(tmp_path / "b.json", max_credits=500, min_interval_s=0)
    assert b.can_request(0)[0] is False  # must be >=1
