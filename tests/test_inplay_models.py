"""Light deterministic tests for research-only in-play baselines. No network."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_models.models import (  # noqa: E402
    M0_StaticB1, M1_TimeScore, M2_RemainingPoisson, M5_Ensemble, full_output_envelope)


def _frame():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(18):
        sd = int(rng.integers(-2, 3)); mn = int(rng.integers(0, 91))
        ed = float(rng.uniform(-150, 150))
        wld = "H" if sd > 0 else ("A" if sd < 0 else "D")
        rows.append({"score_home": max(0, sd), "score_away": max(0, -sd), "score_diff": sd,
                     "decision_minute": mn, "remaining_minutes": max(0, 90 - mn),
                     "elo_delta_home": ed, "red_home": 0, "red_away": 0, "red_diff": 0,
                     "p_home_elo": 0.45, "p_draw_elo": 0.27, "p_away_elo": 0.28, "final_wld": wld})
    return pd.DataFrame(rows)


def test_m0_is_static_prematch():
    df = _frame()
    P = M0_StaticB1().fit(df).predict_wld(df)
    assert np.allclose(P.sum(1), 1.0)
    assert np.allclose(P, P[0], atol=1e-9)   # constant (pre-match elo probs identical across rows)


def test_m2_probs_valid_and_score_responsive():
    lead = pd.DataFrame([{"score_home": 2, "score_away": 0, "score_diff": 2, "decision_minute": 80,
                          "elo_delta_home": 0.0, "red_home": 0, "red_away": 0}])
    P = M2_RemainingPoisson().predict_wld(lead)
    assert np.allclose(P.sum(1), 1.0)
    assert P[0, 0] > 0.8   # 2-0 up at 80' -> home very likely to win


def test_m1_and_m5_fit_predict():
    df = _frame()
    for M in (M1_TimeScore, M5_Ensemble):
        P = M().fit(df).predict_wld(df)
        assert P.shape == (len(df), 3) and np.allclose(P.sum(1), 1.0, atol=1e-6)


def test_full_envelope_has_required_fields_and_research_flag():
    df = _frame()
    P = M2_RemainingPoisson().predict_wld(df)
    env = full_output_envelope(df, P, "M2_remaining_poisson")
    required = ["p_home_win", "p_draw", "p_away_win", "expected_remaining_goals_home",
               "expected_remaining_goals_away", "probability_home_next_goal", "probability_away_next_goal",
               "probability_no_goal_next_5_minutes", "probability_goal_next_1_minutes",
               "probability_goal_next_3_minutes", "probability_goal_next_5_minutes",
               "probability_goal_next_10_minutes", "uncertainty", "entropy", "model_id",
               "model_version", "research_only"]
    for c in required:
        assert c in env.columns, c
    assert env["research_only"].all()
    assert np.allclose(env[["p_home_win", "p_draw", "p_away_win"]].sum(1), 1.0, atol=1e-6)
    # horizon monotonicity: P(goal within 10) >= within 5 >= within 1
    assert (env.probability_goal_next_10_minutes >= env.probability_goal_next_5_minutes - 1e-9).all()
    assert (env.probability_goal_next_5_minutes >= env.probability_goal_next_1_minutes - 1e-9).all()
