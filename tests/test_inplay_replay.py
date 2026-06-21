"""Deterministic behavior tests for the research-only in-play replay layer. No network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.inplay.engine import InPlayState  # noqa: E402
from wcdrawlab.research.inplay_replay import replay_prediction, replay_match, risk_band, pregame_lambdas_from_elo  # noqa: E402


def test_risk_band_thresholds():
    assert risk_band(0.4) == "low"
    assert risk_band(0.7) == "medium"
    assert risk_band(0.95) == "high"


def test_full_time_lead_is_near_certain_and_no_remaining_xg():
    o = replay_prediction(1.4, 1.1, InPlayState(minute=90, goals_a=1, goals_b=0))
    assert o.p_a_win > 0.95
    assert o.p_draw < 0.05
    assert o.remaining_xg_total < 0.1            # no time left -> ~0 remaining goals


def test_kickoff_equal_strength_is_symmetric_with_full_remaining_xg():
    la = lb = 1.3
    o = replay_prediction(la, lb, InPlayState(minute=0, goals_a=0, goals_b=0))
    assert abs(o.p_a_win - o.p_b_win) < 1e-6
    assert abs(o.remaining_xg_total - (la + lb)) < 0.1
    assert o.p_draw_ci_low <= o.p_draw <= o.p_draw_ci_high


def test_red_card_reduces_team_win_probability():
    base = replay_prediction(1.5, 1.2, InPlayState(minute=30, goals_a=0, goals_b=0))
    red_a = replay_prediction(1.5, 1.2, InPlayState(minute=30, goals_a=0, goals_b=0, red_cards_a=1))
    assert red_a.p_a_win < base.p_a_win          # losing a player hurts A's win prob
    assert red_a.p_b_win > base.p_b_win


def test_late_lead_high_win_prob():
    o = replay_prediction(1.3, 1.3, InPlayState(minute=85, goals_a=1, goals_b=0))
    assert o.p_a_win > 0.8


def test_remaining_xg_decreases_through_match():
    early = replay_prediction(1.4, 1.4, InPlayState(minute=10, goals_a=0, goals_b=0))
    late = replay_prediction(1.4, 1.4, InPlayState(minute=70, goals_a=0, goals_b=0))
    assert early.remaining_xg_total > late.remaining_xg_total


def test_replay_match_is_leakage_safe_sequence():
    la, lb = pregame_lambdas_from_elo(120.0)
    snaps = [
        {"minute": 0, "goals_a": 0, "goals_b": 0},
        {"minute": 60, "goals_a": 1, "goals_b": 0},
        {"minute": 90, "goals_a": 1, "goals_b": 0},
    ]
    preds = replay_match(la, lb, snaps)
    assert len(preds) == 3
    # win prob for the leading favorite rises across the sequence; entropy falls by full time
    assert preds[2]["p_a_win"] > preds[0]["p_a_win"]
    assert preds[2]["entropy"] <= preds[0]["entropy"]
    assert all(set(["p_a_win", "p_draw", "p_b_win", "remaining_xg_total", "risk_band"]) <= set(p) for p in preds)
