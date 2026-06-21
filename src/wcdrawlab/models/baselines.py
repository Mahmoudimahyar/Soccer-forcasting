from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from wcdrawlab.ratings import ternary_elo_probs, gaussian_draw_prob
from wcdrawlab.evaluation import normalize_probs, OUTCOME_ORDER


class HistoricalPriorModel:
    def __init__(self):
        self.probs_: np.ndarray | None = None

    def fit(self, y: pd.Series | list[str]):
        counts = pd.Series(y).value_counts(normalize=True)
        self.probs_ = np.array([counts.get(k, 0.0) for k in OUTCOME_ORDER], dtype=float)
        self.probs_ = self.probs_ / self.probs_.sum()
        return self

    def predict_proba(self, n: int | pd.DataFrame):
        if self.probs_ is None:
            raise RuntimeError("Model is not fitted.")
        n_rows = len(n) if hasattr(n, "__len__") and not isinstance(n, int) else int(n)
        return np.tile(self.probs_, (n_rows, 1))


class TernaryEloModel:
    def __init__(self, r: float = 0.4, delta_col: str = "elo_delta", home_advantage: float = 0.0):
        self.r = r
        self.delta_col = delta_col
        self.home_advantage = home_advantage

    def fit(self, X: pd.DataFrame, y=None):
        return self

    def predict_proba(self, X: pd.DataFrame):
        return ternary_elo_probs(X[self.delta_col].values, r=self.r, home_advantage=self.home_advantage)


class GaussianDrawEloModel:
    """Benchmark with Gaussian draw plus Elo expected score split for non-draw mass."""

    def __init__(self, delta_col: str = "elo_delta", draw_base: float = 0.30, draw_width: float = 240.0):
        self.delta_col = delta_col
        self.draw_base = draw_base
        self.draw_width = draw_width

    def fit(self, X: pd.DataFrame, y=None):
        return self

    def predict_proba(self, X: pd.DataFrame):
        delta = X[self.delta_col].values.astype(float)
        p_draw = gaussian_draw_prob(delta, self.draw_base, self.draw_width)
        p_a_cond = 1.0 / (1.0 + 10.0 ** (-delta / 400.0))
        non_draw = 1.0 - p_draw
        p_a = non_draw * p_a_cond
        p_b = non_draw * (1.0 - p_a_cond)
        return normalize_probs(np.vstack([p_a, p_draw, p_b]).T)


class MultinomialLogitModel:
    def __init__(self, features: list[str], C: float = 1.0, max_iter: int = 1000):
        self.features = features
        self.model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=C, max_iter=max_iter, class_weight=None),
        )

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.model.fit(X[self.features].fillna(0), y)
        return self

    def predict_proba(self, X: pd.DataFrame):
        proba = self.model.predict_proba(X[self.features].fillna(0))
        classes = list(self.model[-1].classes_)
        aligned = np.zeros((len(X), 3))
        for j, c in enumerate(OUTCOME_ORDER):
            if c in classes:
                aligned[:, j] = proba[:, classes.index(c)]
        return normalize_probs(aligned)
