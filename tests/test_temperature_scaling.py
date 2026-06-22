"""Tests for temperature-scaling recalibration (research-only in-play model wrapper)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.inplay_models.models import (  # noqa: E402
    temperature_scale, TemperatureScaled, M2fit_FittedPoisson)


def test_temperature_identity_and_monotonicity():
    p = np.array([[0.9, 0.05, 0.05], [0.6, 0.3, 0.1]])
    # T=1 is the identity (within normalization)
    assert np.allclose(temperature_scale(p, 1.0), p, atol=1e-9)
    # T>1 reduces the max probability (less confident); T<1 increases it (more confident)
    assert temperature_scale(p, 2.0)[0].max() < p[0].max()
    assert temperature_scale(p, 0.5)[0].max() > p[0].max()
    # rows stay normalized
    assert np.allclose(temperature_scale(p, 1.7).sum(axis=1), 1.0)


class _FakeOverconfident:
    """Always predicts an overconfident home win regardless of input -> miscalibrated on purpose."""
    model_id = "fake"
    def fit(self, train):
        return self
    def predict_wld(self, df):
        return np.tile([0.9, 0.05, 0.05], (len(df), 1))


def _frame(n=60):
    # true outcomes are only ~40% home wins -> the base is badly overconfident
    rng = np.random.RandomState(0)
    y = rng.choice(["H", "D", "A"], size=n, p=[0.4, 0.3, 0.3])
    return pd.DataFrame({"final_wld": y, "competition": (["A"] * (n // 2) + ["B"] * (n - n // 2))})


def test_temperature_scaled_picks_T_above_one_and_reduces_logloss():
    train = _frame()
    ts = TemperatureScaled(base_factory=_FakeOverconfident).fit(train)
    assert ts.T > 1.0  # tempers an overconfident base
    y = train.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    base = _FakeOverconfident().predict_wld(train)
    cal = ts.predict_wld(train)
    ll = lambda P: -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1)).mean()
    assert ll(cal) < ll(base)  # calibration reduces log-loss for an overconfident model
    assert ts.model_id == "fake_temp"


def _inplay_frame(n=80, seed=0):
    rng = np.random.RandomState(seed)
    delta = rng.uniform(-300, 300, n)
    gh = rng.poisson(1.4 * np.exp(0.25 * delta / 100.0))
    ga = rng.poisson(1.4 * np.exp(-0.25 * delta / 100.0))
    wld = np.where(gh > ga, "H", np.where(ga > gh, "A", "D"))
    return pd.DataFrame({
        "match_id": np.arange(n), "elo_delta_home": delta,
        "final_score_home": gh, "final_score_away": ga, "final_wld": wld,
        "decision_minute": 0.0, "score_home": 0, "score_away": 0, "red_home": 0, "red_away": 0,
    })


def test_m2fit_recovers_goalrate_mapping_from_data():
    m = M2fit_FittedPoisson().fit(_inplay_frame())
    # data generated with base=1.4, k=0.25 -> fitted params should be in the right ballpark
    assert 0.9 < m.base_ < 2.2
    assert m.k_ > 0.05  # home favored when elo_delta>0
    # predictions are valid probability rows
    P = m.predict_wld(_inplay_frame(n=10, seed=1))
    assert P.shape == (10, 3)
    assert np.allclose(P.sum(axis=1), 1.0) and (P >= 0).all()


def test_m2fit_falls_back_to_defaults_on_tiny_data():
    m = M2fit_FittedPoisson().fit(_inplay_frame(n=5))  # < 20 matches -> keep hand-set defaults
    assert m.base_ == 1.35 and m.k_ == 0.20
