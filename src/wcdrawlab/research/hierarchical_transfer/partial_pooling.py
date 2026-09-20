"""T3 / T4 / T5 — the shared-coefficient, partial-pooling, and domain-weighted transfer models.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

These three models all import club TRAIN rows (auxiliary domain) under the temporal cutoff, but they do
it with progressively more domain discipline. The TARGET is always the domain-normalized remaining-goal
RESIDUAL (so a club row's residual is taken relative to the CLUB baseline, an intl row's relative to the
INTL baseline — this is the "domain-normalized targets" requirement). The feature space is always the
Phase-3 stable-feature subset only (domain-shifted columns were already excluded upstream).

  * ``T3SharedStableFeatures``  — ONE shared coefficient vector fit on the pooled (intl + club) residual
    rows over the stable subset. Domain enters only through the per-domain RESIDUAL target (the baseline
    already absorbed the per-domain mean), not through separate coefficients. This is the "fully pooled,
    but domain-normalized" model.

  * ``T4PartialPooling``        — hierarchical: a SHARED coefficient vector (fit on pooled rows) PLUS an
    international-specific DEVIATION vector, shrunk toward zero by a ridge whose strength is chosen by
    in-train cross-fit. The effective intl coefficient is ``shared + deviation``; as the shrinkage -> inf
    the model collapses to T3 (shared only); as it -> 0 it approaches an intl-only fit. The deviation is
    fit on the intl residuals AFTER removing the shared prediction (a partial-pooling decomposition).

  * ``T5DomainWeighted``        — same partial-pooling structure, but each CLUB training row is downweighted
    by a scalar in [0,1] equal to (training-estimated domain-overlap score) * (per-row feature-stability
    coverage). Intl rows keep weight 1. Club rows that share little usable signal contribute little to the
    shared fit. The weights are computed from TRAIN columns only (``domain_overlap_score`` carried by the
    dataset + the fraction of the stable subset present on the row).

All expose ``predict_intensity(row) -> {home, away}`` and ``predict_wdl(row) -> {H,D,A}``. With NO club
rows in a fold (the current materialized intl-only dataset), T3 == pooled-intl, T4's deviation is fit on
all intl residuals (==T3 shared + intl deviation, i.e. a regularized intl model), and T5's weighting is a
no-op over intl rows — each records an honest ``n_train_club = 0`` so downstream ablations see it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import DOMAIN_CLUB, DOMAIN_INTERNATIONAL, T3_SHARED_STABLE_FEATURES, T4_PARTIAL_POOLING, T5_DOMAIN_WEIGHTED
from .models import (
    EPS_INTENSITY,
    RidgePoissonResidual,
    StableFeatureSpace,
    cell_float,
    cross_fit_ridge_lambda,
    current_score_diff,
    remaining_goal_exact_wdl,
    stable_feature_columns,
)


def _domain(r: dict) -> str:
    return r.get("domain") or DOMAIN_INTERNATIONAL


def _intl(rows: Sequence[dict]) -> List[dict]:
    return [r for r in rows if _domain(r) == DOMAIN_INTERNATIONAL]


def _club(rows: Sequence[dict]) -> List[dict]:
    return [r for r in rows if _domain(r) == DOMAIN_CLUB]


def _baseline(row: dict, side: str) -> float:
    col = {"home": "domain_baseline_home", "away": "domain_baseline_away"}[side]
    return cell_float(row, col) or 0.0


# =================================================================================================
# T3 — shared coefficient on the stable subset over domain-normalized residual targets.
# =================================================================================================
@dataclass
class T3SharedStableFeatures:
    model_id: str = T3_SHARED_STABLE_FEATURES
    short_id: str = "T3"
    ridge: float = 1.0
    cols: List[str] = field(default_factory=list)
    home_model: Optional[RidgePoissonResidual] = None
    away_model: Optional[RidgePoissonResidual] = None
    n_train_total: int = 0
    n_train_club: int = 0
    fitted: bool = False

    def fit(self, train_rows: Sequence[dict]) -> "T3SharedStableFeatures":
        pooled = list(train_rows)
        self.cols = stable_feature_columns(pooled)
        self.home_model = RidgePoissonResidual(side="home", ridge=self.ridge).fit(pooled, self.cols)
        self.away_model = RidgePoissonResidual(side="away", ridge=self.ridge).fit(pooled, self.cols)
        self.n_train_total = len(pooled)
        self.n_train_club = len(_club(pooled))
        self.fitted = True
        return self

    def predict_intensity(self, row: dict) -> Dict[str, float]:
        if not self.fitted:
            return {"home": _baseline(row, "home"), "away": _baseline(row, "away")}
        return {"home": self.home_model.intensity(row), "away": self.away_model.intensity(row)}

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        it = self.predict_intensity(row)
        return remaining_goal_exact_wdl(it["home"], it["away"], current_score_diff(row))


# =================================================================================================
# Partial-pooling decomposition: shared fit on pooled rows, then an intl deviation fit on the intl
# residuals AFTER subtracting the shared prediction, shrunk by ``dev_ridge``. Reused by T4 and T5.
# =================================================================================================
@dataclass
class _SharedPlusDeviation:
    """shared + intl-specific deviation for one side. effective_intl(x) = shared(x) + deviation(x)."""
    side: str
    shared: RidgePoissonResidual
    dev_space: StableFeatureSpace
    dev_w: np.ndarray
    dev_ridge: float

    def _dev(self, row: dict) -> float:
        x = np.asarray(self.dev_space.row_vector(row) + [1.0], dtype=float)
        return float(x @ self.dev_w)

    def intensity(self, row: dict, domain: str) -> float:
        base_col = {"home": "domain_baseline_home", "away": "domain_baseline_away"}[self.side]
        base = cell_float(row, base_col) or 0.0
        adj = self.shared.predict_residual(row)
        if domain == DOMAIN_INTERNATIONAL:
            adj += self._dev(row)
        return max(EPS_INTENSITY, base + adj)


def _fit_shared_plus_deviation(side: str, pooled: Sequence[dict], intl: Sequence[dict],
                               cols: Sequence[str], shared_ridge: float, dev_ridge: float,
                               sample_weights: Optional[Sequence[float]] = None) -> _SharedPlusDeviation:
    shared = RidgePoissonResidual(side=side, ridge=shared_ridge).fit(pooled, cols, sample_weights)
    target_col = {"home": "transfer_residual_home", "away": "transfer_residual_away"}[side]
    # deviation target = intl residual MINUS shared prediction (the part the shared model leaves on the table)
    dev_rows, dev_targets = [], []
    for r in intl:
        y = cell_float(r, target_col)
        if y is None:
            continue
        dev_rows.append(r)
        dev_targets.append(y - shared.predict_residual(r))
    dev_space = StableFeatureSpace(list(cols)).fit(dev_rows or list(intl))
    if dev_rows:
        X = dev_space.matrix(dev_rows)
        yv = np.asarray(dev_targets, dtype=float)
        n, d = X.shape
        Xb = np.hstack([X, np.ones((n, 1))])
        pen = np.eye(d + 1) * dev_ridge
        pen[-1, -1] = 0.0
        try:
            dev_w = np.linalg.solve(Xb.T @ Xb + pen, Xb.T @ yv)
        except np.linalg.LinAlgError:
            dev_w = np.linalg.lstsq(Xb.T @ Xb + pen, Xb.T @ yv, rcond=None)[0]
    else:
        dev_w = np.zeros(len(dev_space.names) + 1)
    return _SharedPlusDeviation(side=side, shared=shared, dev_space=dev_space, dev_w=dev_w,
                                dev_ridge=dev_ridge)


# =================================================================================================
# T4 — partial pooling: shared + shrunk intl deviation. dev_ridge chosen by in-train cross-fit.
# =================================================================================================
@dataclass
class T4PartialPooling:
    model_id: str = T4_PARTIAL_POOLING
    short_id: str = "T4"
    shared_ridge: float = 1.0
    dev_ridge: Optional[float] = None       # chosen in-train if None
    cols: List[str] = field(default_factory=list)
    home: Optional[_SharedPlusDeviation] = None
    away: Optional[_SharedPlusDeviation] = None
    n_train_total: int = 0
    n_train_club: int = 0
    chosen_dev_ridge: Optional[float] = None
    fitted: bool = False

    def _choose_dev_ridge(self, intl: Sequence[dict], side: str) -> float:
        # cross-fit the deviation shrinkage on intl residuals (TRAIN only). Larger lambda => more pooling.
        best, _ = cross_fit_ridge_lambda(intl, self.cols, side,
                                         lambdas=(0.3, 1.0, 3.0, 10.0, 30.0, 100.0))
        return best

    def fit(self, train_rows: Sequence[dict]) -> "T4PartialPooling":
        pooled = list(train_rows)
        intl = _intl(pooled)
        self.cols = stable_feature_columns(pooled)
        dr = self.dev_ridge if self.dev_ridge is not None else self._choose_dev_ridge(intl, "home")
        self.chosen_dev_ridge = dr
        self.home = _fit_shared_plus_deviation("home", pooled, intl, self.cols, self.shared_ridge, dr)
        self.away = _fit_shared_plus_deviation("away", pooled, intl, self.cols, self.shared_ridge, dr)
        self.n_train_total = len(pooled)
        self.n_train_club = len(_club(pooled))
        self.fitted = True
        return self

    def predict_intensity(self, row: dict) -> Dict[str, float]:
        if not self.fitted:
            return {"home": _baseline(row, "home"), "away": _baseline(row, "away")}
        # at TEST time the row is international (intl-only test population) -> use the intl effective coeff
        dom = DOMAIN_INTERNATIONAL
        return {"home": self.home.intensity(row, dom), "away": self.away.intensity(row, dom)}

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        it = self.predict_intensity(row)
        return remaining_goal_exact_wdl(it["home"], it["away"], current_score_diff(row))


# =================================================================================================
# T5 — domain-weighted partial pooling. Club rows weighted by overlap * per-row stability coverage.
# =================================================================================================
def _row_stability_coverage(row: dict, cols: Sequence[str]) -> float:
    if not cols:
        return 0.0
    present = sum(1 for c in cols if cell_float(row, "feat_" + c) is not None)
    return present / len(cols)


def domain_weight(row: dict, cols: Sequence[str]) -> float:
    """Training weight for a row: intl rows -> 1.0; club rows -> overlap_score * per-row coverage in
    [0,1]. Computed from TRAIN columns only."""
    if _domain(row) == DOMAIN_INTERNATIONAL:
        return 1.0
    overlap = cell_float(row, "domain_overlap_score")
    overlap = 1.0 if overlap is None else max(0.0, min(1.0, overlap))
    cov = _row_stability_coverage(row, cols)
    return max(0.0, min(1.0, overlap * cov))


@dataclass
class T5DomainWeighted:
    model_id: str = T5_DOMAIN_WEIGHTED
    short_id: str = "T5"
    shared_ridge: float = 1.0
    dev_ridge: Optional[float] = None
    uniform_weights: bool = False           # ablation switch: T5-uniform-vs-overlap-weights
    cols: List[str] = field(default_factory=list)
    home: Optional[_SharedPlusDeviation] = None
    away: Optional[_SharedPlusDeviation] = None
    n_train_total: int = 0
    n_train_club: int = 0
    mean_club_weight: Optional[float] = None
    chosen_dev_ridge: Optional[float] = None
    fitted: bool = False

    def fit(self, train_rows: Sequence[dict]) -> "T5DomainWeighted":
        pooled = list(train_rows)
        intl = _intl(pooled)
        club = _club(pooled)
        self.cols = stable_feature_columns(pooled)
        if self.uniform_weights:
            weights = [1.0] * len(pooled)
        else:
            weights = [domain_weight(r, self.cols) for r in pooled]
        cw = [w for r, w in zip(pooled, weights) if _domain(r) == DOMAIN_CLUB]
        self.mean_club_weight = (float(np.mean(cw)) if cw else None)
        dr = self.dev_ridge
        if dr is None:
            best, _ = cross_fit_ridge_lambda(intl, self.cols, "home",
                                             lambdas=(0.3, 1.0, 3.0, 10.0, 30.0, 100.0))
            dr = best
        self.chosen_dev_ridge = dr
        self.home = _fit_shared_plus_deviation("home", pooled, intl, self.cols, self.shared_ridge, dr,
                                               sample_weights=weights)
        self.away = _fit_shared_plus_deviation("away", pooled, intl, self.cols, self.shared_ridge, dr,
                                               sample_weights=weights)
        self.n_train_total = len(pooled)
        self.n_train_club = len(club)
        self.fitted = True
        return self

    def predict_intensity(self, row: dict) -> Dict[str, float]:
        if not self.fitted:
            return {"home": _baseline(row, "home"), "away": _baseline(row, "away")}
        dom = DOMAIN_INTERNATIONAL
        return {"home": self.home.intensity(row, dom), "away": self.away.intensity(row, dom)}

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        it = self.predict_intensity(row)
        return remaining_goal_exact_wdl(it["home"], it["away"], current_score_diff(row))


__all__ = [
    "T3SharedStableFeatures", "T4PartialPooling", "T5DomainWeighted",
    "domain_weight", "_SharedPlusDeviation", "_fit_shared_plus_deviation",
]
