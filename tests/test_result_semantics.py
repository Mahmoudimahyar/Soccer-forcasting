"""Phase 1 result-semantics tests. Synthetic fixtures/events only; no real data, no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402

H, A = 10, 20


def _fx(ft, et=None, pen=None, fid=1):
    return {"fixture": {"id": fid}, "teams": {"home": {"id": H}, "away": {"id": A}},
            "score": {"fulltime": ft, "extratime": et or {"home": None, "away": None},
                      "penalty": pen or {"home": None, "away": None}}}


def _goal(el, team, detail="Normal Goal", player=1):
    return {"time": {"elapsed": el}, "type": "Goal", "detail": detail, "team": {"id": team}, "player": {"id": player}}


def test_regulation_score():
    ev = [_goal(20, H), _goal(50, H), _goal(70, A)]
    r = RS.canonical_result(_fx({"home": 2, "away": 1}), ev)
    assert (r["event_derived_regulation_home_goals"], r["event_derived_regulation_away_goals"]) == (2, 1)
    assert r["reconciliation_status"] == "exact" and r["final_result_type"] == "regulation"


def test_own_goal_beneficiary_not_inverted():
    # Own Goal team=away -> credited to AWAY directly (the fix); official 0-1
    r = RS.canonical_result(_fx({"home": 0, "away": 1}), [_goal(38, A, "Own Goal")])
    assert (r["event_derived_regulation_home_goals"], r["event_derived_regulation_away_goals"]) == (0, 1)
    assert r["reconciliation_status"] == "exact"


def test_extra_time_separated_from_regulation():
    ev = [_goal(40, H), _goal(80, A), _goal(105, H)]  # 1-1 reg, ET goal home
    r = RS.canonical_result(_fx({"home": 1, "away": 1}, et={"home": 2, "away": 1}), ev)
    assert (r["event_derived_regulation_home_goals"], r["event_derived_regulation_away_goals"]) == (1, 1)
    assert (r["event_derived_extra_time_home_goals"], r["event_derived_extra_time_away_goals"]) == (1, 0)
    assert r["final_result_type"] == "after_extra_time" and r["reconciliation_status"] == "exact"


def test_penalty_shootout_separate_not_regulation():
    ev = [_goal(40, H), _goal(80, A)]  # 1-1 regulation; shootout decides
    r = RS.canonical_result(_fx({"home": 1, "away": 1}, et={"home": 1, "away": 1}, pen={"home": 4, "away": 3}), ev)
    assert r["final_result_type"] == "penalty_shootout"
    assert r["penalty_shootout_home_goals"] == 4
    assert (r["event_derived_regulation_home_goals"], r["event_derived_regulation_away_goals"]) == (1, 1)


def test_penalty_scored_counts():
    r = RS.canonical_result(_fx({"home": 1, "away": 0}), [_goal(50, H, "Penalty")])
    assert r["event_derived_regulation_home_goals"] == 1 and r["reconciliation_status"] == "exact"


def test_penalty_missed_does_not_count():
    r = RS.canonical_result(_fx({"home": 0, "away": 0}), [_goal(50, H, "Missed Penalty")])
    assert r["event_derived_regulation_home_goals"] == 0 and r["reconciliation_status"] == "exact"


def test_var_cancelled_goal_classified():
    ev = [_goal(30, H), _goal(35, H), {"time": {"elapsed": 36}, "type": "Var", "detail": "Goal cancelled",
                                       "team": {"id": H}, "player": {"id": 1}}]
    r = RS.canonical_result(_fx({"home": 1, "away": 0}), ev)  # official only 1 (one was cancelled)
    assert r["reconciliation_status"] == "mismatch"
    assert r["reconciliation_exception_type"] == "VAR_cancelled_or_corrected_goal"


def test_duplicate_event_classified():
    ev = [_goal(30, H), _goal(30, H)]  # duplicate -> over-count vs official 1
    r = RS.canonical_result(_fx({"home": 1, "away": 0}), ev)
    assert r["reconciliation_status"] == "mismatch" and r["reconciliation_exception_type"] == "duplicate_event"


def test_out_of_order_does_not_break_score():
    ev = [_goal(70, H), _goal(10, A)]  # backwards order, correct score 1-1
    r = RS.canonical_result(_fx({"home": 1, "away": 1}), ev)
    assert r["reconciliation_status"] == "exact"  # ordering does not affect the derived score


def test_red_card_and_second_yellow_do_not_affect_score():
    ev = [_goal(20, H), {"time": {"elapsed": 60}, "type": "Card", "detail": "Red Card", "team": {"id": A}, "player": {"id": 7}},
          {"time": {"elapsed": 65}, "type": "Card", "detail": "Yellow Card", "team": {"id": A}, "player": {"id": 8}}]
    r = RS.canonical_result(_fx({"home": 1, "away": 0}), ev)
    assert r["reconciliation_status"] == "exact" and r["event_derived_regulation_home_goals"] == 1


def test_idempotent_replay():
    ev = [_goal(20, H), _goal(80, A)]
    assert RS.canonical_result(_fx({"home": 1, "away": 1}), ev) == RS.canonical_result(_fx({"home": 1, "away": 1}), ev)


def test_no_future_event_leakage_into_regulation():
    # an ET goal (elapsed 105) must NOT enter the regulation window
    ev = [_goal(40, H), _goal(105, H)]
    r = RS.canonical_result(_fx({"home": 1, "away": 0}, et={"home": 2, "away": 0}), ev)
    assert r["event_derived_regulation_home_goals"] == 1  # only the 40' goal
