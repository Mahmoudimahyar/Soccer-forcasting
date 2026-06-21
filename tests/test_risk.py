from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.risk import (
    categorical_variance,
    categorical_covariance,
    probability_standard_error,
    beta_probability_interval,
    add_prediction_risk_columns,
    add_draw_bet_risk_columns,
)


def test_categorical_variance_and_covariance():
    p = np.array([[0.5, 0.3, 0.2]])
    var = categorical_variance(p)
    assert np.allclose(var, [[0.25, 0.21, 0.16]])
    cov = categorical_covariance(p)[0]
    assert np.allclose(np.diag(cov), var[0])
    assert np.isclose(cov[0, 1], -0.15)


def test_probability_interval_contains_p():
    p = np.array([0.30])
    se = probability_standard_error(p, n_eff=100)
    lo, hi = beta_probability_interval(p, n_eff=100)
    assert se[0] > 0
    assert lo[0] < p[0] < hi[0]


def test_add_prediction_risk_columns():
    df = pd.DataFrame({"p_a": [0.5], "p_draw": [0.3], "p_b": [0.2]})
    out = add_prediction_risk_columns(df)
    assert "outcome_sd_draw" in out.columns
    assert "prob_ci_low_draw" in out.columns
    assert "prediction_entropy" in out.columns
    assert out.loc[0, "outcome_sd_draw"] > 0


def test_add_draw_bet_risk_columns_positive_ev():
    df = pd.DataFrame({"p_draw_model": [0.30], "odds_draw": [4.0]})
    out = add_draw_bet_risk_columns(df)
    assert out.loc[0, "draw_bet_ev_per_unit"] > 0
    assert out.loc[0, "draw_bet_sd_per_unit"] > 0
