"""In-train-only probability CALIBRATION (isotonic / logistic).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Per-class calibrators fit INSIDE the training fold only and frozen for predict. They never consult a
test label. Two backends:

  * isotonic  -- monotone non-parametric (reuses the locked DM.IsotonicCalibrator so this phase's
                 isotonic path is identical to the event_process / dynamic_models one).
  * logistic  -- Platt scaling on logit(p) (deterministic 1-D logistic regression; numpy fallback).

For a 3-class WDL distribution, ``WDLCalibrator`` fits one calibrator per class on TRAIN pooled
probability-vs-outcome, transforms each class at predict, then renormalizes to a valid simplex.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from wcdrawlab.research import dynamic_models as DM  # reuse locked isotonic calibrator

CALIBRATION_VERSION = "residual_intensity_calibration_v1"
WDL = ["H", "D", "A"]
EPS = 1e-6


class _LogisticCalibrator:
    """Platt scaling: fit y ~ sigmoid(a*logit(p) + b) by deterministic Newton/IRLS on TRAIN. Frozen."""

    def __init__(self):
        self.a = 1.0
        self.b = 0.0
        self.fitted = False

    def fit(self, p: np.ndarray, y: np.ndarray) -> "_LogisticCalibrator":
        p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
        y = np.asarray(y, dtype=float)
        if len(p) < 4 or len(set(y.tolist())) < 2:
            self.a, self.b, self.fitted = 1.0, 0.0, False
            return self
        z = np.log(p / (1 - p))
        X = np.column_stack([z, np.ones_like(z)])
        w = np.zeros(2)
        for _ in range(50):
            eta = X @ w
            mu = 1.0 / (1.0 + np.exp(-eta))
            g = X.T @ (mu - y)
            s = mu * (1 - mu)
            H = X.T @ (X * s[:, None]) + 1e-6 * np.eye(2)
            try:
                w = w - np.linalg.solve(H, g)
            except np.linalg.LinAlgError:
                break
        self.a, self.b = float(w[0]), float(w[1])
        self.fitted = True
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
        if not self.fitted:
            return p
        z = np.log(p / (1 - p))
        return 1.0 / (1.0 + np.exp(-(self.a * z + self.b)))


def make_calibrator(method: str = "isotonic"):
    if method == "logistic":
        return _LogisticCalibrator()
    return DM.IsotonicCalibrator()


class WDLCalibrator:
    """Per-class WDL calibrator fit on TRAIN pooled (raw prob, outcome) pairs; frozen for predict.
    Renormalizes to a valid simplex. method in {'isotonic','logistic'}."""

    def __init__(self, method: str = "isotonic"):
        self.method = method
        self.cal: Dict[str, object] = {}
        self.fitted = False

    def fit(self, raw_probs: Sequence[Dict[str, float]], outcomes: Sequence[str]) -> "WDLCalibrator":
        if not raw_probs:
            self.fitted = False
            return self
        for k in WDL:
            pk = np.array([float(p.get(k, 0.0)) for p in raw_probs])
            yk = np.array([1.0 if t == k else 0.0 for t in outcomes])
            self.cal[k] = make_calibrator(self.method).fit(pk, yk)
        self.fitted = True
        return self

    def transform_one(self, raw: Dict[str, float]) -> Dict[str, float]:
        if not self.fitted:
            return dict(raw)
        out = {}
        for k in WDL:
            c = self.cal.get(k)
            out[k] = float(c.transform(np.array([float(raw.get(k, 0.0))]))[0]) if c is not None else float(raw.get(k, 0.0))
        s = sum(max(0.0, v) for v in out.values())
        if s <= 0:
            return {k: 1.0 / len(WDL) for k in WDL}
        return {k: max(0.0, out[k]) / s for k in WDL}


class BinaryCalibrator:
    """Single-channel calibrator for binary hazards (next-goal / scoring-window). In-train-only."""

    def __init__(self, method: str = "isotonic"):
        self.method = method
        self.cal = None
        self.fitted = False

    def fit(self, p: Sequence[float], y: Sequence[float]) -> "BinaryCalibrator":
        p = np.asarray(p, dtype=float)
        y = np.asarray(y, dtype=float)
        if len(p) < 4 or len(set(y.tolist())) < 2:
            self.fitted = False
            return self
        self.cal = make_calibrator(self.method).fit(p, y)
        self.fitted = True
        return self

    def transform_one(self, p: float) -> float:
        if not self.fitted or self.cal is None:
            return float(p)
        return float(self.cal.transform(np.array([float(p)]))[0])
