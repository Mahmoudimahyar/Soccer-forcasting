from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression

from wcdrawlab.evaluation import normalize_probs


class DrawLogitCalibrator:
    """Calibrate draw probability while preserving non-draw split.

    Fits a binary draw-vs-not-draw model using model probabilities plus contextual features.
    At prediction time, replaces p_draw and rescales A/B probabilities proportionally.
    """

    def __init__(self, features: list[str], C: float = 1.0):
        self.features = features
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=1000))

    def fit(self, X: pd.DataFrame, y_is_draw: pd.Series | np.ndarray):
        self.model.fit(X[self.features].fillna(0), y_is_draw)
        return self

    def predict_draw(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X[self.features].fillna(0))[:, 1]

    def apply(self, base_probs: np.ndarray, X: pd.DataFrame) -> np.ndarray:
        base_probs = normalize_probs(base_probs)
        p_draw_new = np.clip(self.predict_draw(X), 1e-6, 1 - 1e-6)
        non_draw_base = base_probs[:, [0, 2]].sum(axis=1)
        split_a = np.divide(base_probs[:, 0], non_draw_base, out=np.full(len(base_probs), 0.5), where=non_draw_base > 0)
        p_a = (1.0 - p_draw_new) * split_a
        p_b = (1.0 - p_draw_new) * (1.0 - split_a)
        return normalize_probs(np.vstack([p_a, p_draw_new, p_b]).T)


class IsotonicDrawCalibrator:
    """One-dimensional isotonic calibration for p_draw only."""

    def __init__(self):
        self.iso = IsotonicRegression(out_of_bounds="clip")

    def fit(self, p_draw: np.ndarray, y_is_draw: np.ndarray):
        self.iso.fit(p_draw, y_is_draw)
        return self

    def apply(self, base_probs: np.ndarray) -> np.ndarray:
        base_probs = normalize_probs(base_probs)
        p_draw_new = np.clip(self.iso.predict(base_probs[:, 1]), 1e-6, 1 - 1e-6)
        non_draw_base = base_probs[:, [0, 2]].sum(axis=1)
        split_a = np.divide(base_probs[:, 0], non_draw_base, out=np.full(len(base_probs), 0.5), where=non_draw_base > 0)
        p_a = (1.0 - p_draw_new) * split_a
        p_b = (1.0 - p_draw_new) * (1.0 - split_a)
        return normalize_probs(np.vstack([p_a, p_draw_new, p_b]).T)
