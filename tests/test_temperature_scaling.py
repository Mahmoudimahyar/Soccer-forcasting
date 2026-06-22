"""Tests for temperature-scaling recalibration (research-only in-play model wrapper)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.inplay_models.models import temperature_scale, TemperatureScaled  # noqa: E402


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
