"""Deterministic 2022 replay event-semantics regression tests (Phase 1 / 7B). Synthetic events only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import replay_semantics as RS  # noqa: E402

H, A = "Home", "Away"


def ev(t, detail, team, elapsed, extra=0, pid=None):
    return {"type": t, "detail": detail, "team": {"name": team},
            "time": {"elapsed": elapsed, "extra": extra}, "player": {"id": pid}}


def test_standard_and_penalty_goals():
    e = [ev("Goal", "Normal Goal", H, 10), ev("Goal", "Penalty", A, 30)]
    s = RS.reconcile_goals(e, H, A)
    assert s[H] == 1 and s[A] == 1


def test_own_goal_counts_for_beneficiary_no_inversion():
    # API-Football records own goal with team = BENEFICIARY
    e = [ev("Goal", "Own Goal", H, 50)]
    assert RS.reconcile_goals(e, H, A)[H] == 1 and RS.reconcile_goals(e, H, A)[A] == 0


def test_var_cancelled_goal_not_counted():
    e = [ev("Goal", "Normal Goal", H, 40), ev("Var", "Goal cancelled", H, 40)]
    assert RS.reconcile_goals(e, H, A)[H] == 0


def test_extra_time_counts_but_shootout_separate():
    e = [ev("Goal", "Normal Goal", H, 105)]          # ET goal counts (<=120)
    assert RS.reconcile_goals(e, H, A)[H] == 1
    # a shootout pen at minute 120+ via events must NOT inflate regulation score
    e2 = e + [ev("Goal", "Penalty", A, 125)]
    assert RS.reconcile_goals(e2, H, A)[A] == 0
    # shootout score comes from fixture score, kept separate
    assert RS.shootout_score({"penalty": {"home": 4, "away": 3}}) == (4, 3)
    assert RS.shootout_score({"penalty": {"home": None, "away": None}}) is None


def test_second_yellow_and_direct_red():
    e = [ev("Card", "Second Yellow card", H, 70), ev("Card", "Red Card", A, 80),
         ev("Card", "Yellow Card", H, 20)]
    c = RS.count_cards(e, H, A)
    assert c[H]["second_yellow"] == 1 and c[H]["red"] == 1 and c[H]["yellow"] == 1
    assert c[A]["red"] == 1 and c[A]["second_yellow"] == 0


def test_duplicate_events_deduped():
    g = ev("Goal", "Normal Goal", H, 10, pid=7)
    e = [g, dict(g)]   # exact duplicate
    assert RS.reconcile_goals(e, H, A)[H] == 2          # raw counts both
    assert RS.reconcile_goals(RS.dedupe_events(e), H, A)[H] == 1  # deduped counts once


def test_out_of_order_detected_but_reconciles():
    e = [ev("Goal", "Normal Goal", H, 80), ev("Goal", "Normal Goal", A, 20)]
    assert RS.is_chronological(e) is False               # raw order flagged
    assert RS.reconcile_goals(e, H, A) == {H: 1, A: 1}   # sum is order-independent


def test_no_future_event_leakage():
    e = [ev("Goal", "Normal Goal", H, 30), ev("Goal", "Normal Goal", A, 75)]
    future = RS.no_future_event_in_decision(e, decision_minute=60)
    assert len(future) == 1 and future[0]["time"]["elapsed"] == 75
    # state at minute 60 must exclude the 75' goal
    pre = [x for x in e if x not in future]
    assert RS.reconcile_goals(pre, H, A) == {H: 1, A: 0}


def test_reconcile_match_ok_and_exception():
    ok = RS.reconcile_match([ev("Goal", "Normal Goal", H, 10)], H, A, {"home": 1, "away": 0})
    assert ok["reconciles_exact"] and ok["quality_status"] == "ok"
    bad = RS.reconcile_match([ev("Goal", "Normal Goal", H, 10)], H, A, {"home": 2, "away": 0})
    assert not bad["reconciles_exact"] and bad["quality_status"] == "exception"
