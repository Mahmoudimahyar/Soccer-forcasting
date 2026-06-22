"""Deterministic tests for the reusable in-play evaluation framework. No network."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.research import inplay_eval as E  # noqa: E402


def test_rps_perfect_and_worst():
    P = np.array([[1.0, 0.0, 0.0]]); assert E.rps_per_row(P, np.array([0]))[0] == 0.0
    Pw = np.array([[0.0, 0.0, 1.0]]); assert E.rps_per_row(Pw, np.array([0]))[0] == 1.0


def test_logloss_and_brier():
    P = np.array([[0.7, 0.2, 0.1], [0.2, 0.6, 0.2]]); y = np.array([0, 1])
    assert abs(E.logloss_per_row(P, y).mean() - (-(np.log(0.7) + np.log(0.6)) / 2)) < 1e-9
    assert E.draw_brier(P, y) >= 0.0


def test_ece_perfect_is_zero():
    p = np.array([0.0, 0.0, 1.0, 1.0]); y = np.array([0, 0, 1, 1])
    assert E.ece(p, y, bins=2) < 1e-9


def test_calibration_slope_recovers_identity():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 4000); y = (rng.uniform(size=4000) < p).astype(int)  # well-calibrated
    slope, intercept = E.calibration_slope_intercept(p, y)
    assert 0.7 < slope < 1.3 and abs(intercept) < 0.4


def test_paired_match_bootstrap_detects_better():
    # model A strictly lower loss on every match -> a_better_sig True
    mids = np.repeat(np.arange(20), 5)
    a = np.full(100, 0.10); b = np.full(100, 0.20)
    r = E.paired_match_bootstrap(a, b, mids)
    assert r["a_better_sig"] is True and r["delta_mean"] < 0
    # equal -> not significant
    r2 = E.paired_match_bootstrap(a, a, mids)
    assert r2["a_better_sig"] is False and r2["a_worse_sig"] is False
