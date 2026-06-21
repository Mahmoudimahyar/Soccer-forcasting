"""Deterministic tests for the research-only scoreline layer. No network, no real API."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.research.scoreline import ScorelineModel  # noqa: E402


def test_symmetry_at_zero_delta():
    m = ScorelineModel(mode="poisson")
    o = m.outputs_for(0.0)
    assert abs(o.p_a_win - o.p_b_win) < 1e-9
    assert abs(o.expected_goals_a - o.expected_goals_b) < 1e-9
    assert abs((o.p_a_win + o.p_draw + o.p_b_win) - 1.0) < 1e-9


def test_outputs_are_valid_probabilities():
    m = ScorelineModel(mode="poisson")
    o = m.outputs_for(150.0)
    for p in [o.p_a_win, o.p_draw, o.p_b_win, o.p_00, o.p_11, o.p_22,
              o.p_under_15, o.p_under_25, o.p_btts_no]:
        assert 0.0 <= p <= 1.0
    assert o.p_under_15 <= o.p_under_25            # nested events
    assert o.p_draw_ci_low <= o.p_draw <= o.p_draw_ci_high
    assert o.expected_goals_a > o.expected_goals_b  # favorite (positive delta) scores more


def test_p00_matches_independent_poisson():
    m = ScorelineModel(mode="poisson")
    la, lb = m.lambdas(np.array([0.0]))
    o = m.outputs_for(0.0)
    assert abs(o.p_00 - float(np.exp(-la[0] - lb[0]))) < 1e-3  # truncation-normalized


def test_predict_proba_rows_sum_to_one():
    m = ScorelineModel(mode="poisson")
    X = pd.DataFrame({"elo_delta": [-200.0, 0.0, 120.0, 300.0]})
    P = m.predict_proba(X)
    assert P.shape == (4, 3)
    assert np.allclose(P.sum(axis=1), 1.0, atol=1e-9)


def test_fit_recovers_positive_beta_from_synthetic_goals():
    rng = np.random.default_rng(0)
    delta = rng.uniform(-250, 250, size=4000)
    d = delta / 100.0
    la = np.exp(0.30 + 0.50 * d)
    lb = np.exp(0.30 - 0.50 * d)
    ga = rng.poisson(la); gb = rng.poisson(lb)
    m = ScorelineModel(mode="poisson").fit(delta, ga, gb)
    assert 0.30 < m.beta < 0.75            # ~recovers the true 0.50
    assert abs(m.mu - 0.30) < 0.15
    assert m.n_train == 4000


def test_dixon_coles_fits_and_outputs_valid():
    rng = np.random.default_rng(1)
    delta = rng.uniform(-200, 200, size=2000)
    d = delta / 100.0
    ga = rng.poisson(np.exp(0.3 + 0.4 * d)); gb = rng.poisson(np.exp(0.3 - 0.4 * d))
    m = ScorelineModel(mode="dixon_coles").fit(delta, ga, gb)
    o = m.outputs_for(50.0)
    assert abs((o.p_a_win + o.p_draw + o.p_b_win) - 1.0) < 1e-9
    assert -0.2 <= m.rho <= 0.2
