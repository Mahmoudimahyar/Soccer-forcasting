"""AGENT-EDITABLE FILE for autoresearch.

Claude Code may modify this file only. It receives a leakage-safe feature matrix from
`runner.py`, and must return regulation-time probabilities ordered [team_a_win, draw,
team_b_win]. Any candidate must be deterministic under the passed random seed.

Accepted experiments:
  cycle 1 (2026-06-20): standardized regularized multinomial logit on pre-kickoff strength +
    group-state features, BLENDED with the parameter-free ternary-Elo probabilities. The Elo
    prior stabilizes a small World-Cup-only training set.
  cycle 3 (2026-06-20): raised ELO_BLEND_WEIGHT 0.50 -> 0.85. Motivated by the 2022 backtest
    with REAL market odds and the 2026 prequential, both of which showed the 0.50-blend
    candidate was *over-softened* (worse than plain Elo out-of-sample). A blend-weight sweep on
    the fixed selection folds confirmed 0.85 is best: dev+gate composite 0.3892 -> 0.3852,
    improving BOTH 2018 (0.3591 -> 0.3541) and 2022 (0.4194 -> 0.4162) with no regression, and
    edging pure Elo (1.0 -> 0.3860). The model is now mostly Elo's sharpness with a 15% logit
    touch for draw calibration. The market remains the benchmark we do not beat.
  See notes/research/20260620_cycle_1.md, _cycle_3.md, backtest_2022_market.csv.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from wcdrawlab.evaluation import normalize_probs
from wcdrawlab.ratings import ternary_elo_probs


FEATURES = [
    # strength
    "elo_delta",
    "abs_elo_delta",
    # tournament state
    "matchday",
    "prior_group_draws",
    "prior_group_goals_per_match",
    "group_state_points_delta",
    "group_state_gd_delta",
    # market (carried with missingness; zero-filled until real odds exist)
    "p_a_market",
    "p_draw_market",
    "p_b_market",
    "market_total_goals",
    # research proxies
    "low_block_risk",
    "travel_fatigue",
]

# Blend weight on the parameter-free ternary-Elo probabilities. Raised 0.5 -> 0.85 in cycle 3
# (out-of-sample evidence: the candidate was over-softened; Elo is the robust core).
ELO_BLEND_WEIGHT = 0.85


class CandidateModel:
    """Standardized regularized multinomial logit blended with ternary-Elo.

    The Elo blend is a robust prior: it keeps the model honest when the World-Cup-only
    training data is too small for the logit to estimate well. Public API is fixed:
    fit(X, y) / predict_proba(X) -> (n, 3) in [team_a_win, draw, team_b_win].
    """

    def __init__(self, random_state: int = 7) -> None:
        self.random_state = random_state
        self.columns: list[str] = []
        self.scaler = StandardScaler()
        self.model = LogisticRegression(max_iter=2000, C=0.5, random_state=random_state)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "CandidateModel":
        self.columns = [c for c in FEATURES if c in X.columns]
        if not self.columns:
            self.columns = ["elo_delta"]
            X = X.copy()
            X["elo_delta"] = 0.0
        design = X.reindex(columns=self.columns, fill_value=0.0).fillna(0.0)
        scaled = self.scaler.fit_transform(design)
        label_map = {"A": 0, "D": 1, "B": 2, 0: 0, 1: 1, 2: 2}
        encoded = y.map(label_map) if isinstance(y, pd.Series) else y
        self.model.fit(scaled, encoded.astype(int))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        design = X.reindex(columns=self.columns, fill_value=0.0).fillna(0.0)
        scaled = self.scaler.transform(design)
        raw = self.model.predict_proba(scaled)
        full = np.full((len(X), 3), 1e-9, dtype=float)
        for idx, cls in enumerate(self.model.classes_):
            full[:, int(cls)] = raw[:, idx]
        logit_probs = normalize_probs(full)

        # Blend with the parameter-free ternary-Elo prior for robustness.
        if ELO_BLEND_WEIGHT > 0 and "elo_delta" in X.columns:
            elo_delta = X["elo_delta"].to_numpy(dtype=float)
            elo_probs = ternary_elo_probs(elo_delta)
            blended = (1.0 - ELO_BLEND_WEIGHT) * logit_probs + ELO_BLEND_WEIGHT * elo_probs
            return normalize_probs(blended)
        return logit_probs
