from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.ratings import ternary_elo_probs, gaussian_draw_prob
from wcdrawlab.models.scoreline import poisson_score_matrix, probs_from_score_matrix
from wcdrawlab.market import no_vig_from_decimal_odds, kelly_fraction


def test_ternary_elo_probs_sum_to_one():
    p = ternary_elo_probs(np.array([-200, 0, 200]), r=0.4)
    assert p.shape == (3, 3)
    assert np.allclose(p.sum(axis=1), 1.0)
    assert p[1, 1] > p[0, 1]


def test_gaussian_draw_peak():
    p0 = gaussian_draw_prob(0)
    p300 = gaussian_draw_prob(300)
    assert p0 > p300


def test_score_matrix_probs():
    m = poisson_score_matrix(1.2, 1.1, max_goals=8)
    assert np.isclose(m.sum(), 1.0)
    p = probs_from_score_matrix(m)
    assert np.isclose(p.sum(), 1.0)


def test_no_vig():
    p = no_vig_from_decimal_odds(pd.Series([2.0]), pd.Series([3.5]), pd.Series([4.0]))
    assert np.allclose(p.sum(axis=1), 1.0)


def test_kelly_nonnegative():
    f = kelly_fraction(0.30, 3.8, fraction=0.25)
    assert f >= 0
