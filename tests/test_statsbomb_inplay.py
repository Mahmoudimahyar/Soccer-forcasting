"""Leakage-safety + determinism tests for the StatsBomb in-play builder. Synthetic events; no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.statsbomb_inplay import (  # noqa: E402
    extract_events, starting_xi, build_match, events_sha256, GRID)

EVENTS = [
    {"type": {"name": "Shot"}, "team": {"name": "Beta"}, "minute": 20,
     "shot": {"statsbomb_xg": 0.2, "outcome": {"name": "Saved"}}},
    {"type": {"name": "Foul Committed"}, "team": {"name": "Beta"}, "minute": 25,
     "foul_committed": {"card": {"name": "Yellow Card"}}},
    {"type": {"name": "Shot"}, "team": {"name": "Alpha"}, "minute": 30,
     "shot": {"statsbomb_xg": 0.5, "outcome": {"name": "Goal"}}},
    {"type": {"name": "Foul Committed"}, "team": {"name": "Alpha"}, "minute": 60,
     "foul_committed": {"card": {"name": "Red Card"}}},
    {"type": {"name": "Substitution"}, "team": {"name": "Alpha"}, "minute": 65},
    {"type": {"name": "Own Goal For"}, "team": {"name": "Beta"}, "minute": 70},
]
COV = {"lineup": True, "xg": True, "player_ids": True, "d360": False, "events_ok": True}


def _build():
    return build_match(extract_events(EVENTS), "Alpha", "Beta", sb_match_id=1, match_date="2022-12-01",
                       competition_id="WC2022", competition_type="international", confederation="FIFA",
                       elo_delta_home=50.0, p_elo=(0.45, 0.27, 0.28), coverage=COV, src_sha="abc")


def test_extract_events_provider_semantics():
    ex = extract_events(EVENTS)
    assert sorted(ex["goals"]) == [(30, "Alpha"), (70, "Beta")]  # shot-goal + own-goal-for beneficiary
    assert (60, "Alpha", "Red Card") in ex["cards"] and (25, "Beta", "Yellow Card") in ex["cards"]
    assert ex["subs"] == [(65, "Alpha")] and len(ex["shots"]) == 2


def test_state_uses_only_events_strictly_before_decision_minute():
    state, ng, card, sub, mt = _build()
    by_min = {r["decision_minute"]: r for r in state}
    # goal at 30 must NOT be in score at m=30 (strict <), but IS at m=35
    assert by_min[30]["score_home"] == 0 and by_min[35]["score_home"] == 1
    # live xG: away shot at 20 counts from m=25; home shot(=goal) at 30 counts from m=35
    assert abs(by_min[25]["live_xg_away"] - 0.2) < 1e-9 and by_min[30]["live_xg_home"] == 0.0
    assert abs(by_min[35]["live_xg_home"] - 0.5) < 1e-9
    # red at 60 -> red_home from m=65; sub at 65 -> subs_home from m=70 (strict <)
    assert by_min[60]["red_home"] == 0 and by_min[65]["red_home"] == 1
    assert by_min[65]["subs_home"] == 0 and by_min[70]["subs_home"] == 1


def test_targets_are_future_and_correctly_ordered():
    state, ng, card, sub, mt = _build()
    ngm = {r["decision_minute"]: r["next_goal_team"] for r in ng}
    assert ngm[5] == "H"      # first future goal is Alpha @30
    assert ngm[35] == "A"     # next future goal is Beta own-goal @70
    assert ngm[75] == "NONE"  # no goal at/after 75
    assert mt["final_wld"] == "D" and mt["final_score_home"] == 1 and mt["final_score_away"] == 1


def test_deterministic_rebuild_and_source_hash():
    a = _build(); b = _build()
    assert a[0] == b[0] and a[1] == b[1] and a[4] == b[4]  # identical state + targets + match row
    assert events_sha256("x") == events_sha256("x") and events_sha256("x") != events_sha256("y")
    assert all(r["source_events_sha256"] == "abc" for r in a[0])  # provenance traceability


def test_cross_match_isolation():
    s1 = _build()[0]
    # a different match with no events -> independent zero state (no bleed from match 1)
    s2 = build_match({"goals": [], "cards": [], "subs": [], "shots": []}, "Gamma", "Delta",
                     sb_match_id=2, match_date="2022-12-02", competition_id="WC2022",
                     competition_type="international", confederation="FIFA", elo_delta_home=0.0,
                     p_elo=(0.4, 0.3, 0.3), coverage=COV, src_sha="zzz")[0]
    assert all(r["score_home"] == 0 and r["score_away"] == 0 for r in s2)
    assert {r["sb_match_id"] for r in s1} == {1} and {r["sb_match_id"] for r in s2} == {2}


def test_starting_xi_parses_player_ids():
    lineups = [{"team_name": "Alpha", "lineup": [
        {"player_id": 7, "positions": [{"from": "00:00", "start_reason": "Starting XI"}]},
        {"player_id": 9, "positions": [{"from": "61:00", "start_reason": "Substitution"}]}]}]
    xi = starting_xi(lineups)
    assert xi["Alpha"] == [7]  # only the 00:00 starter
    assert GRID[0] == 5 and GRID[-1] == 95
