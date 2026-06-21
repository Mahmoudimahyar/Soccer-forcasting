"""Deterministic reconciliation tests on sanitized local fixtures only. No real API calls."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.ingestion.reconcile import reconcile_events, priority, is_critical  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "reconciliation" / "critical_events.json"


def _load():
    return json.loads(FIX.read_text(encoding="utf-8"))["candidates"]


def _find(results, match_id, event_type, team_id, minute_near):
    return [r for r in results
            if r["match_id"] == match_id and r["event_type"] == event_type
            and r["team_id"] == team_id and abs((r["minute"] or 0) - minute_near) <= 2]


def test_agreeing_goal_is_reconciled_and_eligible():
    res = reconcile_events(_load(), tolerance_minutes=1)
    g = _find(res, "MX1", "goal", "TA", 23)
    assert len(g) == 1
    assert g[0]["reconciliation_status"] == "reconciled"
    assert g[0]["source_confidence"] == "high"
    assert g[0]["approved_feature_eligible"] is True
    # canonical taken from the highest-priority source (official_feed beats football_data_org)
    assert g[0]["canonical_source"] == "official_feed"
    assert sorted(g[0]["contributing_sources"]) == ["football_data_org", "official_feed"]


def test_conflicting_scorer_is_unresolved_and_blocked():
    res = reconcile_events(_load(), tolerance_minutes=1)
    g = _find(res, "MX1", "goal", "TB", 55)
    assert len(g) == 1
    assert g[0]["reconciliation_status"] == "unresolved"
    assert "player_id" in g[0]["provider_disagreement"]
    assert g[0]["approved_feature_eligible"] is False  # critical + unresolved -> excluded


def test_single_source_substitution_is_flagged_not_blocked():
    res = reconcile_events(_load(), tolerance_minutes=1)
    s = _find(res, "MX1", "substitution", "TA", 70)
    assert len(s) == 1
    assert s[0]["reconciliation_status"] == "single_source"
    assert s[0]["approved_feature_eligible"] is True   # uncorroborated != conflicting
    assert s[0]["source_confidence"] in {"medium", "low"}


def test_red_card_within_tolerance_merges():
    res = reconcile_events(_load(), tolerance_minutes=1)
    r = _find(res, "MX1", "red_card", "TB", 80)
    assert len(r) == 1  # minute 80 vs 81 within tolerance -> one canonical event
    assert r[0]["reconciliation_status"] == "reconciled"


def test_kickoff_time_disagreement_is_unresolved():
    res = reconcile_events(_load(), tolerance_minutes=1)
    k = [r for r in res if r["event_type"] == "kickoff"]
    assert len(k) == 1
    assert k[0]["reconciliation_status"] == "unresolved"
    assert "kickoff_utc" in k[0]["provider_disagreement"]
    assert k[0]["approved_feature_eligible"] is False


def test_minute_beyond_tolerance_splits_into_two_events():
    cands = [
        {"source_name": "official_feed", "match_id": "MZ", "event_type": "goal", "team_id": "T1", "minute": 10, "player_id": "a"},
        {"source_name": "api_football", "match_id": "MZ", "event_type": "goal", "team_id": "T1", "minute": 40, "player_id": "b"},
    ]
    res = reconcile_events(cands, tolerance_minutes=1)
    assert len(res) == 2  # 30-minute gap -> two distinct events, each single_source
    assert all(r["reconciliation_status"] == "single_source" for r in res)


def test_non_critical_disagreement_not_blocked():
    cands = [
        {"source_name": "api_football", "match_id": "MZ", "event_type": "shot", "team_id": "T1", "minute": 12, "player_id": "a"},
        {"source_name": "secondary_provider", "match_id": "MZ", "event_type": "shot", "team_id": "T1", "minute": 12, "player_id": "b"},
    ]
    res = reconcile_events(cands, tolerance_minutes=1)
    assert len(res) == 1
    assert is_critical("shot") is False
    # shot is non-critical: even with a player disagreement it is not hard-blocked
    assert res[0]["approved_feature_eligible"] is True


def test_priority_order():
    assert priority("official_feed") < priority("api_football") < priority("football_data_org") < priority("open_dataset")
    assert priority("totally_unknown_source") == 9
