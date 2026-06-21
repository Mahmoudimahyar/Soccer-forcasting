from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from wcdrawlab.evaluation import normalize_probs


def poisson_score_matrix(lambda_a: float, lambda_b: float, max_goals: int = 8) -> np.ndarray:
    goals = np.arange(max_goals + 1)
    pa = poisson.pmf(goals, lambda_a)
    pb = poisson.pmf(goals, lambda_b)
    mat = np.outer(pa, pb)
    # Put omitted tail mass into last row/col approximately.
    mat[-1, :] += max(0.0, 1.0 - pa.sum()) * pb
    mat[:, -1] += max(0.0, 1.0 - pb.sum()) * pa
    mat = mat / mat.sum()
    return mat


def probs_from_score_matrix(mat: np.ndarray) -> np.ndarray:
    p_a = float(np.tril(mat, -1).sum())  # rows goals_a > cols goals_b? Actually tril below diagonal: row > col.
    p_b = float(np.triu(mat, 1).sum())
    p_d = float(np.trace(mat))
    return np.array([p_a, p_d, p_b])


def dixon_coles_tau(i: int, j: int, lambda_a: float, lambda_b: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor."""
    if i == 0 and j == 0:
        return 1.0 - lambda_a * lambda_b * rho
    if i == 0 and j == 1:
        return 1.0 + lambda_a * rho
    if i == 1 and j == 0:
        return 1.0 + lambda_b * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def adjusted_score_matrix(lambda_a: float, lambda_b: float, max_goals: int = 8, rho: float = 0.0, diagonal_inflation: float = 0.0) -> np.ndarray:
    mat = poisson_score_matrix(lambda_a, lambda_b, max_goals=max_goals)
    if rho != 0.0:
        for i in range(min(2, max_goals + 1)):
            for j in range(min(2, max_goals + 1)):
                mat[i, j] *= max(0.001, dixon_coles_tau(i, j, lambda_a, lambda_b, rho))
    if diagonal_inflation != 0.0:
        for k in range(max_goals + 1):
            mat[k, k] *= (1.0 + diagonal_inflation)
    mat = mat / mat.sum()
    return mat


class IndependentPoissonModel:
    """Fit separate Poisson regressions for team A and team B goals."""

    def __init__(self, features: list[str], max_goals: int = 8, alpha: float = 1e-4, rho: float = 0.0, diagonal_inflation: float = 0.0):
        self.features = features
        self.max_goals = max_goals
        self.alpha = alpha
        self.rho = rho
        self.diagonal_inflation = diagonal_inflation
        self.model_a = make_pipeline(StandardScaler(), PoissonRegressor(alpha=alpha, max_iter=1000))
        self.model_b = make_pipeline(StandardScaler(), PoissonRegressor(alpha=alpha, max_iter=1000))

    def fit(self, X: pd.DataFrame, y_goals_a: pd.Series, y_goals_b: pd.Series):
        x = X[self.features].fillna(0)
        self.model_a.fit(x, y_goals_a)
        self.model_b.fit(x, y_goals_b)
        return self

    def predict_lambdas(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = X[self.features].fillna(0)
        la = np.clip(self.model_a.predict(x), 0.05, 8.0)
        lb = np.clip(self.model_b.predict(x), 0.05, 8.0)
        return la, lb

    def predict_score_matrices(self, X: pd.DataFrame) -> list[np.ndarray]:
        la, lb = self.predict_lambdas(X)
        return [adjusted_score_matrix(a, b, self.max_goals, rho=self.rho, diagonal_inflation=self.diagonal_inflation) for a, b in zip(la, lb)]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        mats = self.predict_score_matrices(X)
        return normalize_probs(np.vstack([probs_from_score_matrix(m) for m in mats]))


def score_cluster_probability(mat: np.ndarray, scores: list[tuple[int, int]]) -> float:
    total = 0.0
    for a, b in scores:
        if a < mat.shape[0] and b < mat.shape[1]:
            total += mat[a, b]
    return float(total)
