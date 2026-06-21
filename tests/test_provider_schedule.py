"""Tests for the provider interface (quota guard) + quota-aware scheduler. No network."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.providers.interface import (  # noqa: E402
    QuotaBudget, QuotaExceeded, MatchDataProvider, APIFootballProvider,
)
from wcdrawlab.providers.schedule import plan_fetches, LINEUP, STANDINGS, EVENTS  # noqa: E402

NOW = datetime(2026, 6, 21, 18, 0, tzinfo=timezone.utc)


def test_quota_budget_consume_and_fail_closed():
    b = QuotaBudget(daily_limit=3)
    assert b.remaining() == 3 and b.can(3) and not b.can(4)
    b.consume(2); assert b.remaining() == 1
    with pytest.raises(QuotaExceeded):
        b.consume(2)
    b.consume(1); assert b.remaining() == 0


def test_quota_reserve_protects_headroom():
    b = QuotaBudget(daily_limit=10, reserve=4)
    assert b.remaining() == 6


def test_lineup_scheduled_only_in_window():
    far = [{"match_id": "m1", "kickoff_utc": NOW + timedelta(minutes=120), "status": "scheduled"}]
    win = [{"match_id": "m1", "kickoff_utc": NOW + timedelta(minutes=75), "status": "scheduled"}]
    assert plan_fetches(far, QuotaBudget(), NOW) == []
    assert plan_fetches(win, QuotaBudget(), NOW) == [("m1", LINEUP)]


def test_standings_only_after_finished():
    sched = [{"match_id": "m1", "kickoff_utc": NOW - timedelta(hours=5), "status": "scheduled"}]
    fin = [{"match_id": "m1", "kickoff_utc": NOW - timedelta(hours=5), "status": "finished"}]
    assert all(ft != STANDINGS for _, ft in plan_fetches(sched, QuotaBudget(), NOW))
    plan = plan_fetches(fin, QuotaBudget(), NOW)
    assert ("m1", STANDINGS) in plan and ("m1", EVENTS) in plan  # final whistle -> both


def test_events_only_on_state_change_when_live():
    quiet = [{"match_id": "m1", "kickoff_utc": NOW - timedelta(minutes=30), "status": "live", "state_changed": False}]
    changed = [{"match_id": "m1", "kickoff_utc": NOW - timedelta(minutes=30), "status": "live", "state_changed": True}]
    assert plan_fetches(quiet, QuotaBudget(), NOW) == []          # no continuous polling
    assert plan_fetches(changed, QuotaBudget(), NOW) == [("m1", EVENTS)]


def test_already_fetched_not_rescheduled():
    win = [{"match_id": "m1", "kickoff_utc": NOW + timedelta(minutes=75), "status": "scheduled", "fetched": [LINEUP]}]
    assert plan_fetches(win, QuotaBudget(), NOW) == []


def test_budget_caps_and_priority_lineup_first():
    states = [
        {"match_id": "f1", "kickoff_utc": NOW - timedelta(hours=3), "status": "finished"},          # standings+events
        {"match_id": "L1", "kickoff_utc": NOW + timedelta(minutes=75), "status": "scheduled"},      # lineup
    ]
    plan = plan_fetches(states, QuotaBudget(daily_limit=1), NOW)
    assert plan == [("L1", LINEUP)]   # only 1 slot -> lineup (priority 1) wins


def test_interface_protocol_and_quota_metering():
    class FakeClient:
        def fixture_lineups(self, fid): return {"lineup": fid}
        def fixtures(self, l, s): return {}
        def fixture_events(self, fid): return {}
        def fixture_statistics(self, fid): return {}
        def standings(self, l, s): return {}
    p = APIFootballProvider(budget=QuotaBudget(daily_limit=1))
    p._client = FakeClient()
    assert isinstance(p, MatchDataProvider)
    assert p.lineups(123) == {"lineup": 123}
    assert p.budget.used == 1
    with pytest.raises(QuotaExceeded):
        p.events(123)   # budget exhausted -> fail closed
