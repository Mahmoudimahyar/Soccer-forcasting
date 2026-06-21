"""Research-only pre-match scoreline layer (transparent, leakage-safe).

Two variants:
  - independent Poisson (mode="poisson")
  - Dixon-Coles low-score / draw-inflation (mode="dixon_coles")

Goal intensities are mapped from the leakage-safe `elo_delta` and calibrated by Poisson MLE on
TRAIN goals only:  log lambda_a = mu + beta*d,  log lambda_b = mu - beta*d,  d = elo_delta/100.
Dixon-Coles adds a low-score dependence parameter rho.

This module is NOT a runtime-approved model (B1/Elo remains the only approved model). It provides the
scoreline / total-goals deliverables: expected goals, score matrix, exact-score and over/under and
BTTS probabilities, plus a transparent draw uncertainty interval. The 1X2 it implies is reported for
ablation only — it is not promoted unless it clears the frozen promotion protocol.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


def _dc_tau(a, b, la, lb, rho):
    """Dixon-Coles low-score adjustment (a, b in {0,1} only)."""
    if a == 0 and b == 0:
        return 1.0 - la * lb * rho
    if a == 0 and b == 1:
        return 1.0 + la * rho
    if a == 1 and b == 0:
        return 1.0 + lb * rho
    if a == 1 and b == 1:
        return 1.0 - rho
    return 1.0


@dataclass
class ScorelineOutputs:
    expected_goals_a: float
    expected_goals_b: float
    p_a_win: float
    p_draw: float
    p_b_win: float
    p_00: float
    p_11: float
    p_22: float
    p_under_15: float
    p_under_25: float
    p_btts_no: float
    p_draw_se: float
    p_draw_ci_low: float
    p_draw_ci_high: float


class ScorelineModel:
    def __init__(self, mode: str = "poisson", max_goals: int = 10):
        assert mode in {"poisson", "dixon_coles"}
        self.mode = mode
        self.max_goals = max_goals
        self.mu = np.log(1.30)   # ~avg goals/team prior
        self.beta = 0.20
        self.rho = 0.0
        self.n_train = 0

    # ---- calibration (train goals only) ----
    def fit(self, elo_delta, goals_a, goals_b) -> "ScorelineModel":
        d = np.asarray(elo_delta, dtype=float) / 100.0
        ga = np.asarray(goals_a, dtype=float)
        gb = np.asarray(goals_b, dtype=float)
        ok = np.isfinite(d) & np.isfinite(ga) & np.isfinite(gb)
        d, ga, gb = d[ok], ga[ok], gb[ok]
        self.n_train = int(len(d))
        if self.n_train < 10:
            return self

        def nll(params):
            mu, beta = params[0], params[1]
            la = np.exp(mu + beta * d)
            lb = np.exp(mu - beta * d)
            ll = (ga * np.log(la) - la) + (gb * np.log(lb) - lb)
            if self.mode == "dixon_coles":
                rho = params[2]
                # low-score cells only
                for mask, fn in [((ga == 0) & (gb == 0), lambda la, lb: 1 - la * lb * rho),
                                 ((ga == 0) & (gb == 1), lambda la, lb: 1 + la * rho),
                                 ((ga == 1) & (gb == 0), lambda la, lb: 1 + lb * rho),
                                 ((ga == 1) & (gb == 1), lambda la, lb: np.full_like(la, 1 - rho))]:
                    if mask.any():
                        tau = np.clip(fn(la[mask], lb[mask]), 1e-6, None)
                        ll[mask] += np.log(tau)
            return -np.sum(ll)

        x0 = [self.mu, self.beta] + ([0.0] if self.mode == "dixon_coles" else [])
        bounds = [(np.log(0.5), np.log(3.0)), (0.0, 1.5)] + ([(-0.2, 0.2)] if self.mode == "dixon_coles" else [])
        res = minimize(nll, x0, method="L-BFGS-B", bounds=bounds)
        self.mu, self.beta = float(res.x[0]), float(res.x[1])
        if self.mode == "dixon_coles":
            self.rho = float(res.x[2])
        return self

    # ---- lambdas + score matrix ----
    def lambdas(self, elo_delta) -> tuple[np.ndarray, np.ndarray]:
        d = np.asarray(elo_delta, dtype=float) / 100.0
        return np.exp(self.mu + self.beta * d), np.exp(self.mu - self.beta * d)

    def _score_matrix(self, la: float, lb: float) -> np.ndarray:
        g = np.arange(self.max_goals + 1)
        m = np.outer(poisson.pmf(g, la), poisson.pmf(g, lb))
        if self.mode == "dixon_coles":
            for a in (0, 1):
                for b in (0, 1):
                    m[a, b] *= _dc_tau(a, b, la, lb, self.rho)
        return m / m.sum()

    # ---- full outputs for one match ----
    def outputs_for(self, elo_delta_value: float) -> ScorelineOutputs:
        la, lb = self.lambdas(np.array([elo_delta_value]))
        la, lb = float(la[0]), float(lb[0])
        m = self._score_matrix(la, lb)
        idx = np.arange(self.max_goals + 1)
        total = idx[:, None] + idx[None, :]
        p_a = float(np.tril(m, -1).sum())   # a > b
        p_b = float(np.triu(m, 1).sum())    # b > a
        p_d = float(np.trace(m))
        p_a, p_d, p_b = (np.array([p_a, p_d, p_b]) / (p_a + p_d + p_b)).tolist()
        n = max(1, self.n_train)
        se = float(np.sqrt(p_d * (1 - p_d) / n))
        return ScorelineOutputs(
            expected_goals_a=la, expected_goals_b=lb,
            p_a_win=p_a, p_draw=p_d, p_b_win=p_b,
            p_00=float(m[0, 0]), p_11=float(m[1, 1]), p_22=float(m[2, 2]),
            p_under_15=float(m[total <= 1].sum()), p_under_25=float(m[total <= 2].sum()),
            p_btts_no=float(m[0, :].sum() + m[:, 0].sum() - m[0, 0]),
            p_draw_se=se, p_draw_ci_low=max(0.0, p_d - 1.96 * se), p_draw_ci_high=min(1.0, p_d + 1.96 * se),
        )

    def predict_proba(self, X) -> np.ndarray:
        """1X2 (n,3) for ablation against the frozen evaluator's metrics. X has 'elo_delta'."""
        import pandas as pd
        delta = X["elo_delta"].to_numpy(dtype=float) if isinstance(X, pd.DataFrame) else np.asarray(X, dtype=float)
        out = np.zeros((len(delta), 3))
        for i, dv in enumerate(delta):
            o = self.outputs_for(float(dv))
            out[i] = [o.p_a_win, o.p_draw, o.p_b_win]
        return out
