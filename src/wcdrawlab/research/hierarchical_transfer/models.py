"""Core numeric building blocks for the hierarchical transfer ladder.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module holds the small, deterministic, dependency-light primitives the T1..T7 models share:

  * ``RidgePoissonResidual`` — a ridge-penalized LINEAR regressor on the Phase-3 stable-feature subset
    whose TARGET is the domain-normalized remaining-goal RESIDUAL (observed remaining goals minus the
    per-domain baseline intensity). It predicts a residual *adjustment* per side; the model's expected
    remaining-goal intensity is ``domain_baseline + adjustment`` (floored at a small epsilon). Fitting is
    a closed-form ridge normal-equation solve (numpy), so it is exactly reproducible and needs no RNG.
    Penalty is applied to non-intercept weights only; features are standardized on TRAIN statistics.

  * ``feature_matrix`` — pull the ``feat_<col>`` stable-subset values out of dataset rows, preserving
    missingness via a per-column mean-impute (TRAIN means) + an ``__unknown`` indicator (same contract as
    ``dynamic_models.FeatureSpace`` so the two engines stay comparable).

  * ``remaining_goal_mc_wdl`` — convert a pair of expected REMAINING-goal intensities (home, away) at the
    decision minute into P(final H/D/A) by Monte-Carlo simulation of independent Poisson remaining goals
    added to the CURRENT score. Deterministic (seeded numpy Generator). This is the simulation layer T7
    uses; an exact closed-form Poisson-difference fallback (``remaining_goal_exact_wdl``) is used for the
    self-tests so they need no large MC budget.

Everything here is leakage-free by construction: the residual target and the per-domain baseline are
computed upstream (Phase 3) on TRAIN rows only; this module only *reads* the columns the dataset carries.
No completed-2026 row ever reaches a fit (the eval layer + dataset builder assert that).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# Stable-feature subset columns are stored on each dataset row as ``feat_<col>``.
FEAT_PREFIX = "feat_"
EPS_INTENSITY = 1e-4   # floor on any predicted remaining-goal intensity (Poisson lambda must be >= 0)


# =================================================================================================
# numeric cell access (preserve missingness; never coerce a missing cell to 0)
# =================================================================================================
def cell_float(row: dict, key: str) -> Optional[float]:
    if key not in row:
        return None
    v = row.get(key)
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in ("none", "nan", "null"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def stable_feature_columns(rows: Sequence[dict]) -> List[str]:
    """The ordered list of stable-feature *base* names present as ``feat_<col>`` on the rows. Determined
    from the first row that has any feat columns (the Phase-3 builder writes the same subset on every
    row of a fold)."""
    for r in rows:
        cols = sorted(k[len(FEAT_PREFIX):] for k in r.keys() if k.startswith(FEAT_PREFIX))
        if cols:
            return cols
    return []


# =================================================================================================
# Feature matrix builder (mean-impute on TRAIN + unknown indicator). Mirrors dynamic_models.FeatureSpace.
# =================================================================================================
@dataclass
class StableFeatureSpace:
    cols: List[str]
    means: Dict[str, float] = field(default_factory=dict)
    stds: Dict[str, float] = field(default_factory=dict)

    @property
    def names(self) -> List[str]:
        out: List[str] = []
        for c in self.cols:
            out += [c, c + "__unknown"]
        return out

    def fit(self, train_rows: Sequence[dict]) -> "StableFeatureSpace":
        for c in self.cols:
            vals = [v for v in (cell_float(r, FEAT_PREFIX + c) for r in train_rows) if v is not None]
            self.means[c] = float(np.mean(vals)) if vals else 0.0
            sd = float(np.std(vals)) if len(vals) > 1 else 0.0
            self.stds[c] = sd if sd > 1e-9 else 1.0
        return self

    def row_vector(self, row: dict) -> List[float]:
        vec: List[float] = []
        for c in self.cols:
            v = cell_float(row, FEAT_PREFIX + c)
            if v is None:
                vec += [0.0, 1.0]   # standardized-imputed value == 0 (the mean), unknown flag 1
            else:
                vec += [(v - self.means.get(c, 0.0)) / self.stds.get(c, 1.0), 0.0]
        return vec

    def matrix(self, rows: Sequence[dict]) -> np.ndarray:
        if not rows:
            return np.zeros((0, len(self.names)), dtype=float)
        return np.asarray([self.row_vector(r) for r in rows], dtype=float)


# =================================================================================================
# Ridge linear regressor on the residual target (closed-form normal equations). Deterministic.
# =================================================================================================
@dataclass
class RidgePoissonResidual:
    """Ridge LINEAR regression of the domain-normalized remaining-goal RESIDUAL on the standardized
    stable-feature subset. ``side`` is 'home' / 'away' / 'total'. The prediction is the residual
    adjustment; ``intensity`` adds it to the per-row domain baseline and floors at EPS.

    Closed form: w = (X'X + lam*I_pen)^-1 X'y with a bias column (unpenalized). lam = ridge strength
    chosen by the caller (T4/T5 pick it via in-train cross-fit; T1/T3 use a fixed default). Sample
    weights (T5 domain weighting) enter as a diagonal W in the normal equations."""

    side: str = "total"
    ridge: float = 1.0
    space: Optional[StableFeatureSpace] = None
    weights: Optional[np.ndarray] = None         # learned coefficients (incl. bias as last entry)
    fitted: bool = False
    n_train: int = 0
    target_col: str = "transfer_residual_total"

    def _target_column(self) -> str:
        return {"home": "transfer_residual_home", "away": "transfer_residual_away",
                "total": "transfer_residual_total"}.get(self.side, "transfer_residual_total")

    def fit(self, train_rows: Sequence[dict], cols: Sequence[str],
            sample_weights: Optional[Sequence[float]] = None) -> "RidgePoissonResidual":
        self.target_col = self._target_column()
        space = StableFeatureSpace(list(cols)).fit(train_rows)
        usable = [(r, cell_float(r, self.target_col)) for r in train_rows]
        usable = [(r, y) for (r, y) in usable if y is not None]
        if sample_weights is not None:
            sw_map = list(sample_weights)
        if not usable:
            self.space = space
            self.weights = np.zeros(len(space.names) + 1)
            self.fitted = True
            self.n_train = 0
            return self
        X = space.matrix([r for r, _ in usable])
        y = np.asarray([yv for _, yv in usable], dtype=float)
        n, d = X.shape
        Xb = np.hstack([X, np.ones((n, 1))])           # bias column last
        if sample_weights is not None and len(sw_map) == len(train_rows):
            # align weights to the usable subset
            keep_idx = [i for i, r in enumerate(train_rows) if cell_float(r, self.target_col) is not None]
            w = np.asarray([sw_map[i] for i in keep_idx], dtype=float)
            w = np.clip(w, 0.0, None)
        else:
            w = np.ones(n, dtype=float)
        Wd = w[:, None]
        A = Xb.T @ (Wd * Xb)
        pen = np.eye(d + 1) * self.ridge
        pen[-1, -1] = 0.0                               # do not penalize bias
        b = Xb.T @ (w * y)
        try:
            self.weights = np.linalg.solve(A + pen, b)
        except np.linalg.LinAlgError:
            self.weights = np.linalg.lstsq(A + pen, b, rcond=None)[0]
        self.space = space
        self.fitted = True
        self.n_train = n
        return self

    def predict_residual(self, row: dict) -> float:
        if not self.fitted or self.space is None or self.weights is None:
            return 0.0
        x = np.asarray(self.space.row_vector(row) + [1.0], dtype=float)
        return float(x @ self.weights)

    def intensity(self, row: dict) -> float:
        """Expected remaining goals for ``side`` = domain baseline + residual adjustment, floored."""
        base_col = {"home": "domain_baseline_home", "away": "domain_baseline_away",
                    "total": "domain_baseline_total"}[self.side]
        base = cell_float(row, base_col)
        if base is None:
            base = 0.0
        return max(EPS_INTENSITY, base + self.predict_residual(row))


def cross_fit_ridge_lambda(train_rows: Sequence[dict], cols: Sequence[str], side: str,
                           lambdas: Sequence[float] = (0.1, 0.3, 1.0, 3.0, 10.0, 30.0),
                           k: int = 3) -> Tuple[float, Dict[float, float]]:
    """Pick the ridge strength that minimizes held-out residual MSE under a deterministic k-fold split
    of the TRAIN rows (split by a stable hash of match_id so all snapshots of a match stay together).
    Returns (best_lambda, {lambda: mean_cv_mse}). TRAIN ONLY — no test row participates."""
    target_col = {"home": "transfer_residual_home", "away": "transfer_residual_away",
                  "total": "transfer_residual_total"}.get(side, "transfer_residual_total")
    rows = [r for r in train_rows if cell_float(r, target_col) is not None]
    if len(rows) < (2 * k):
        # too small to cross-fit -> default mid lambda
        return 1.0, {}
    # group by match so folds are match-disjoint
    def _mid(r):
        return str(r.get("match_id") or r.get("source_match_id") or id(r))
    match_ids = sorted({_mid(r) for r in rows})
    fold_of = {m: (abs(hash(m)) % k) for m in match_ids}
    scores: Dict[float, List[float]] = {lam: [] for lam in lambdas}
    for f in range(k):
        tr = [r for r in rows if fold_of[_mid(r)] != f]
        te = [r for r in rows if fold_of[_mid(r)] == f]
        if not tr or not te:
            continue
        for lam in lambdas:
            m = RidgePoissonResidual(side=side, ridge=lam).fit(tr, cols)
            errs = []
            for r in te:
                y = cell_float(r, target_col)
                if y is None:
                    continue
                errs.append((m.predict_residual(r) - y) ** 2)
            if errs:
                scores[lam].append(float(np.mean(errs)))
    mean_scores = {lam: (float(np.mean(v)) if v else float("inf")) for lam, v in scores.items()}
    best = min(mean_scores, key=mean_scores.get) if mean_scores else 1.0
    return best, mean_scores


# =================================================================================================
# Remaining-goal -> W/D/L conversion. Both an exact Poisson-difference closed form (for tests / default)
# and a seeded Monte-Carlo (the T7 simulation layer). Both add remaining goals to the CURRENT score.
# =================================================================================================
def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def current_score_diff(row: dict) -> int:
    gd = cell_float(row, "feat_goals_diff")
    if gd is None:
        gd = cell_float(row, "state_score_diff_signed")
    if gd is None:
        gh, ga = cell_float(row, "goals_home"), cell_float(row, "goals_away")
        gd = (gh - ga) if (gh is not None and ga is not None) else 0.0
    return int(round(gd))


def remaining_goal_exact_wdl(lam_home: float, lam_away: float, score_diff_now: int,
                             kmax: int = 10) -> Dict[str, float]:
    """Closed-form P(final H/D/A): sum over remaining home/away Poisson goals added to current score.
    Deterministic, no RNG. ``score_diff_now`` is current (home - away)."""
    lam_home = max(0.0, lam_home)
    lam_away = max(0.0, lam_away)
    pH = pD = pA = 0.0
    for fh in range(0, kmax + 1):
        ph = _poisson_pmf(fh, lam_home)
        for fa in range(0, kmax + 1):
            p = ph * _poisson_pmf(fa, lam_away)
            d = score_diff_now + fh - fa
            if d > 0:
                pH += p
            elif d == 0:
                pD += p
            else:
                pA += p
    s = pH + pD + pA
    if s <= 0:
        return {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
    return {"H": pH / s, "D": pD / s, "A": pA / s}


def remaining_goal_mc_wdl(lam_home: float, lam_away: float, score_diff_now: int,
                          n_sims: int = 4000, seed: int = 12345) -> Dict[str, float]:
    """Monte-Carlo P(final H/D/A): simulate independent Poisson remaining goals added to the current
    score. Seeded numpy Generator -> deterministic for a given (lambdas, score, seed, n_sims)."""
    lam_home = max(0.0, lam_home)
    lam_away = max(0.0, lam_away)
    rng = np.random.default_rng(seed)
    gh = rng.poisson(lam_home, size=n_sims)
    ga = rng.poisson(lam_away, size=n_sims)
    d = score_diff_now + gh - ga
    pH = float(np.mean(d > 0))
    pD = float(np.mean(d == 0))
    pA = float(np.mean(d < 0))
    return {"H": pH, "D": pD, "A": pA}


__all__ = [
    "FEAT_PREFIX", "EPS_INTENSITY", "cell_float", "stable_feature_columns",
    "StableFeatureSpace", "RidgePoissonResidual", "cross_fit_ridge_lambda",
    "current_score_diff", "remaining_goal_exact_wdl", "remaining_goal_mc_wdl",
]
