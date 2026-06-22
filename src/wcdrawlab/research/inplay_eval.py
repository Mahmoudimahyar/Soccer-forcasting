"""Reusable leakage-aware evaluation framework for in-play / pre-match research (research-only).

Match-level (not row-level) bootstrap; calibration; reliability; breakdowns. Pure functions.
Outcome index convention: 0=home/A, 1=draw, 2=away/B (3-way) for the proper scores.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rps_per_row(P, y_idx):
    oh = np.eye(P.shape[1])[y_idx]
    return ((np.cumsum(P, 1) - np.cumsum(oh, 1)) ** 2).sum(1) / (P.shape[1] - 1)


def logloss_per_row(P, y_idx):
    return -np.log(np.clip(P[np.arange(len(P)), y_idx], 1e-12, 1))


def draw_brier(P, y_idx, draw_col=1):
    return float(((P[:, draw_col] - (y_idx == draw_col).astype(float)) ** 2).mean())


def binary_brier(p, y):
    return float(((np.asarray(p) - np.asarray(y)) ** 2).mean())


def binary_logloss(p, y):
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12); y = np.asarray(y, float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def ece(p, y, bins=10):
    p = np.asarray(p, float); y = np.asarray(y, float); edges = np.linspace(0, 1, bins + 1); tot = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if m.any():
            tot += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(tot)


def reliability_table(p, y, bins=5):
    p = np.asarray(p, float); y = np.asarray(y, float); edges = np.linspace(0, 1, bins + 1); rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if m.any():
            rows.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": int(m.sum()),
                         "mean_pred": round(float(p[m].mean()), 4), "obs_rate": round(float(y[m].mean()), 4)})
    return pd.DataFrame(rows)


def calibration_slope_intercept(p_draw, y_draw):
    """Logistic recalibration of draw prob -> (slope, intercept). slope~1, intercept~0 = well-calibrated."""
    from sklearn.linear_model import LogisticRegression
    p = np.clip(np.asarray(p_draw, float), 1e-6, 1 - 1e-6)
    z = np.log(p / (1 - p)).reshape(-1, 1); y = np.asarray(y_draw, int)
    if len(np.unique(y)) < 2:
        return float("nan"), float("nan")
    lr = LogisticRegression().fit(z, y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def match_level_bootstrap(per_row_metric, match_ids, B=2000, seed=0):
    """Mean of a per-row metric aggregated to per-match, with a match-level bootstrap 95% CI."""
    s = pd.Series(per_row_metric).groupby(np.asarray(match_ids)).mean()
    rng = np.random.default_rng(seed); vals = s.to_numpy(); n = len(vals)
    bs = vals[rng.integers(0, n, size=(B, n))].mean(1)
    return {"mean": float(vals.mean()), "ci_low": float(np.percentile(bs, 2.5)),
            "ci_high": float(np.percentile(bs, 97.5)), "n_matches": int(n)}


def paired_match_bootstrap(metric_a, metric_b, match_ids, B=2000, seed=0):
    """Per-match mean delta (a-b) with bootstrap CI. Negative => a better (for loss metrics)."""
    d = pd.Series(np.asarray(metric_a) - np.asarray(metric_b)).groupby(np.asarray(match_ids)).mean()
    rng = np.random.default_rng(seed); vals = d.to_numpy(); n = len(vals)
    bs = vals[rng.integers(0, n, size=(B, n))].mean(1)
    lo, hi = float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
    return {"delta_mean": float(vals.mean()), "ci_low": lo, "ci_high": hi,
            "a_better_sig": hi < 0, "a_worse_sig": lo > 0, "n_matches": int(n)}
