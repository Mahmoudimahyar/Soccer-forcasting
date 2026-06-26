"""Player-impact MODEL families (Phase 4/5). research_only / experimental / not_runtime_approved.

Transparent, regularized predictors that are fit INSIDE each training fold only (regularization strength
selected by internal cross-validation on the TRAIN rows -- never on test). No NN / transformer / LLM.

Families (all consume the per-row snapshot dicts produced by scripts/research_jobs/_common.regulation_snapshots,
optionally augmented with player-impact feature fields supplied per row by the player_history module):

  W/D/L (ordered 3-class):
    W2  remaining-time Poisson reference (reimplemented here; does NOT import the frozen prospective M2).
    P1  W2-logit anchor + PRE-MATCH starting-XI player-impact difference (+ uncertainty / coverage).
    P2  P1 + CURRENT on-pitch player-impact difference.
    P3  P2 + substitution-delta history (net impact swapped on via subs).
    P4  P3 + team-state (cards / sendings-off / score / remaining etc.).

  Next goal (binary P(goal in next 15')):
    N0  base rate.
    N1  time / score / card / sub hazard.
    N2  N1 + on-pitch player-impact diff.
    N3  N2 + substitution-delta.

  Discipline (binary; gate on >=150 positives):
    C0  base rate.
    C1  C0 + discipline history.

  xG fusion (W/D/L on the xG-matched subset):
    X0  W2-on-matched-subset (Poisson reference restricted to rows that carry xG-event-state).
    X1  W2 + xG event-state features.
    X2  W2 + player-impact features.
    X3  W2 + player-impact + xG.

Graceful degradation: every model declares the feature columns it wants. For each wanted column a row that
lacks the value (missing / None / NaN) is imputed with the TRAIN mean and flagged with a companion
`<col>__unknown` indicator (1.0 when imputed). A row with no information at all therefore reduces to the
W2 / base-rate anchor rather than crashing. The imputation statistics are learned on TRAIN only.

Determinism: sklearn solvers are seeded (random_state=0, deterministic liblinear / lbfgs); feature order is
fixed; no RNG is consulted at predict time.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

MODEL_VERSION = "player_impact_models_v1"
W2_BASE = 1.35  # goals per team per 90' (remaining-time Poisson reference; reimplemented, NOT imported from M2)
WDL = ["H", "D", "A"]

# ----------------------------------------------------------------------------------------------------
# Per-row player-impact / xG feature names. Models degrade gracefully when these are absent on a row.
# These are the columns the player_history module is expected to attach; nothing here requires them.
# ----------------------------------------------------------------------------------------------------
PREMATCH_IMPACT_COLS = ["prematch_impact_diff", "prematch_impact_uncertainty", "prematch_impact_coverage"]
ONPITCH_IMPACT_COLS = ["onpitch_impact_diff"]
SUBDELTA_IMPACT_COLS = ["sub_impact_delta"]
TEAMSTATE_COLS = ["score_diff", "card_diff", "so_diff", "subs_diff", "player_count_diff", "remaining"]
XG_EVENT_COLS = ["xg_diff_before", "roll5_xg_diff", "roll10_xg_diff",
                 "shotcount5_diff", "shotcount10_diff", "tsl_shot", "tsl_major"]
DISCIPLINE_HIST_COLS = ["team_card_rate_prior", "opp_card_rate_prior", "fouls_diff"]


def _norm(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(d.values()) or 1.0
    return {k: v / s for k, v in d.items()}


# ----------------------------------------------------------------------------------------------------
# W2 remaining-time Poisson reference (reimplemented; parameter-free, no fitting, no leakage)
# ----------------------------------------------------------------------------------------------------
def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def w2_poisson(row: dict) -> Dict[str, float]:
    """P(final H/D/A) from the current regulation score diff + remaining minutes. Parameter-free."""
    rem = max(0, int(row.get("remaining", 0)))
    lam = W2_BASE * rem / 90.0
    diff0 = int(row.get("score_diff", 0))
    pH = pD = pA = 0.0
    for fh in range(0, 8):
        ph = _poisson_pmf(fh, lam)
        for fa in range(0, 8):
            p = ph * _poisson_pmf(fa, lam)
            d = diff0 + fh - fa
            if d > 0:
                pH += p
            elif d == 0:
                pD += p
            else:
                pA += p
    return _norm({"H": pH, "D": pD, "A": pA})


def _w2_logit_anchor(row: dict, eps: float = 1e-6) -> List[float]:
    """W2 probabilities as 2 log-odds offsets (H vs D, A vs D) -- a leakage-free anchor feature for P*/X*."""
    p = w2_poisson(row)
    pd_ = max(eps, p["D"])
    return [math.log(max(eps, p["H"]) / pd_), math.log(max(eps, p["A"]) / pd_)]


# ----------------------------------------------------------------------------------------------------
# Feature assembly with graceful unknown handling (impute on TRAIN means + unknown indicator)
# ----------------------------------------------------------------------------------------------------
def _raw_value(row: dict, col: str):
    v = row.get(col, None)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


class _FeatureSpace:
    """Fixed-order feature builder. For each requested column it emits the (imputed) value and a companion
    `<col>__unknown` indicator. Imputation means are learned on TRAIN only and frozen for predict."""

    def __init__(self, cols: Sequence[str], with_w2_anchor: bool = True):
        self.cols = list(cols)
        self.with_w2_anchor = with_w2_anchor
        self.means: Dict[str, float] = {}

    @property
    def names(self) -> List[str]:
        out: List[str] = []
        if self.with_w2_anchor:
            out += ["w2_logit_H", "w2_logit_A"]
        for c in self.cols:
            out += [c, c + "__unknown"]
        return out

    def fit(self, train_rows: Sequence[dict]) -> "_FeatureSpace":
        for c in self.cols:
            vals = [v for v in (_raw_value(r, c) for r in train_rows) if v is not None]
            self.means[c] = float(np.mean(vals)) if vals else 0.0
        return self

    def row_vector(self, row: dict) -> List[float]:
        vec: List[float] = []
        if self.with_w2_anchor:
            vec += _w2_logit_anchor(row)
        for c in self.cols:
            v = _raw_value(row, c)
            if v is None:
                vec += [self.means.get(c, 0.0), 1.0]
            else:
                vec += [v, 0.0]
        return vec

    def matrix(self, rows: Sequence[dict]) -> np.ndarray:
        if not rows:
            return np.zeros((0, len(self.names)), dtype=float)
        return np.asarray([self.row_vector(r) for r in rows], dtype=float)


# ----------------------------------------------------------------------------------------------------
# Regularized fitters. Regularization strength chosen by internal CV on TRAIN ONLY.
# ----------------------------------------------------------------------------------------------------
_C_GRID = [0.03, 0.1, 0.3, 1.0, 3.0]


def _internal_folds(n: int, k: int = 3, seed: int = 0):
    """Deterministic k-fold index split (no RNG state leak across calls)."""
    idx = np.arange(n)
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    return [idx[i::k] for i in range(k)]


class _RidgeLogitMulti:
    """Ridge / elastic-net multinomial logistic. C selected by internal CV (mean val log-loss) on train."""

    def __init__(self, space: _FeatureSpace, l1_ratio: float = 0.0):
        self.space = space
        self.l1_ratio = l1_ratio
        self.model = None
        self.scaler_mean = None
        self.scaler_std = None
        self.classes_: List[str] = []
        self.fallback: Optional[Dict[str, float]] = None

    def _standardize_fit(self, X: np.ndarray):
        self.scaler_mean = X.mean(axis=0)
        self.scaler_std = X.std(axis=0)
        self.scaler_std[self.scaler_std == 0] = 1.0

    def _standardize(self, X: np.ndarray) -> np.ndarray:
        return (X - self.scaler_mean) / self.scaler_std

    def _make(self, C: float):
        from sklearn.linear_model import LogisticRegression
        if self.l1_ratio and self.l1_ratio > 0:
            return LogisticRegression(C=C, penalty="elasticnet", l1_ratio=self.l1_ratio,
                                      solver="saga", max_iter=4000, random_state=0)
        return LogisticRegression(C=C, penalty="l2", solver="lbfgs", max_iter=2000, random_state=0)

    def fit(self, train_rows: Sequence[dict], target_key: str = "target_wdl") -> "_RidgeLogitMulti":
        self.space.fit(train_rows)
        X = self.space.matrix(train_rows)
        y = np.asarray([r[target_key] for r in train_rows])
        classes = sorted(set(y.tolist()))
        self.classes_ = classes
        if len(classes) < 2 or len(y) < 6:
            # degenerate train: fall back to base rate
            self.fallback = _base_rate(train_rows, target_key, classes if classes else WDL)
            return self
        self._standardize_fit(X)
        Xs = self._standardize(X)
        bestC, best = _C_GRID[0], math.inf
        folds = _internal_folds(len(y), k=min(3, max(2, len(y) // 4)))
        for C in _C_GRID:
            tot, cnt = 0.0, 0
            for fi in range(len(folds)):
                va = folds[fi]
                tr = np.concatenate([folds[j] for j in range(len(folds)) if j != fi])
                if len(set(y[tr].tolist())) < 2 or len(va) == 0:
                    continue
                m = self._make(C).fit(Xs[tr], y[tr])
                P = m.predict_proba(Xs[va])
                ll = _safe_logloss(P, y[va], m.classes_)
                tot += ll * len(va)
                cnt += len(va)
            if cnt and tot / cnt < best:
                best, bestC = tot / cnt, C
        self.model = self._make(bestC).fit(Xs, y)
        self.selected_C = bestC
        return self

    def predict_one(self, row: dict) -> Dict[str, float]:
        if self.model is None:
            return dict(self.fallback or _norm({k: 1.0 for k in (self.classes_ or WDL)}))
        x = self._standardize(self.space.matrix([row]))
        p = self.model.predict_proba(x)[0]
        out = {cls: 0.0 for cls in WDL}
        for i, cls in enumerate(self.model.classes_):
            out[cls] = float(p[i])
        return _norm({k: out.get(k, 0.0) for k in WDL})


class _RidgeLogitBin:
    """Ridge / elastic-net binary logistic for hazard / discipline targets. C selected by internal CV on train."""

    def __init__(self, space: _FeatureSpace, l1_ratio: float = 0.0):
        self.space = space
        self.l1_ratio = l1_ratio
        self.model = None
        self.scaler_mean = None
        self.scaler_std = None
        self.base = 0.5

    def _standardize_fit(self, X):
        self.scaler_mean = X.mean(axis=0); self.scaler_std = X.std(axis=0)
        self.scaler_std[self.scaler_std == 0] = 1.0

    def _standardize(self, X):
        return (X - self.scaler_mean) / self.scaler_std

    def _make(self, C):
        from sklearn.linear_model import LogisticRegression
        if self.l1_ratio and self.l1_ratio > 0:
            return LogisticRegression(C=C, penalty="elasticnet", l1_ratio=self.l1_ratio,
                                      solver="saga", max_iter=4000, random_state=0)
        return LogisticRegression(C=C, penalty="l2", solver="lbfgs", max_iter=2000, random_state=0)

    def fit(self, train_rows: Sequence[dict], target_key: str) -> "_RidgeLogitBin":
        self.space.fit(train_rows)
        X = self.space.matrix(train_rows)
        y = np.asarray([int(r[target_key]) for r in train_rows])
        self.base = float(y.mean()) if len(y) else 0.5
        if len(set(y.tolist())) < 2 or len(y) < 6:
            self.model = None
            return self
        self._standardize_fit(X); Xs = self._standardize(X)
        bestC, best = _C_GRID[0], math.inf
        folds = _internal_folds(len(y), k=min(3, max(2, len(y) // 4)))
        for C in _C_GRID:
            tot, cnt = 0.0, 0
            for fi in range(len(folds)):
                va = folds[fi]
                tr = np.concatenate([folds[j] for j in range(len(folds)) if j != fi])
                if len(set(y[tr].tolist())) < 2 or len(va) == 0:
                    continue
                m = self._make(C).fit(Xs[tr], y[tr])
                p = np.clip(m.predict_proba(Xs[va])[:, 1], 1e-9, 1 - 1e-9)
                ll = float(-np.mean(y[va] * np.log(p) + (1 - y[va]) * np.log(1 - p)))
                tot += ll * len(va); cnt += len(va)
            if cnt and tot / cnt < best:
                best, bestC = tot / cnt, C
        self.model = self._make(bestC).fit(Xs, y)
        self.selected_C = bestC
        return self

    def predict_one(self, row: dict) -> float:
        if self.model is None:
            return float(self.base)
        x = self._standardize(self.space.matrix([row]))
        return float(np.clip(self.model.predict_proba(x)[0][1], 1e-9, 1 - 1e-9))


# ----------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------
def _safe_logloss(P: np.ndarray, y: np.ndarray, classes, eps: float = 1e-12) -> float:
    cls_idx = {c: i for i, c in enumerate(classes)}
    tot = 0.0
    for j in range(len(y)):
        tot += -math.log(max(eps, float(P[j][cls_idx[y[j]]])))
    return tot / max(1, len(y))


def _base_rate(train_rows: Sequence[dict], target_key: str, classes) -> Dict[str, float]:
    c = {k: 0.0 for k in classes}
    for r in train_rows:
        t = r.get(target_key)
        if t in c:
            c[t] += 1.0
    return _norm({k: v + 1e-6 for k, v in c.items()})


# ----------------------------------------------------------------------------------------------------
# Public family factories. Each returns {name: predict(row)->probs}, fit on TRAIN rows only.
# ----------------------------------------------------------------------------------------------------
def wdl_predictors(train_rows: Sequence[dict], target_key: str = "target_wdl") -> Dict[str, Callable]:
    """W2 (reference) + P1..P4 fitted on train competitions only."""
    p1 = _RidgeLogitMulti(_FeatureSpace(PREMATCH_IMPACT_COLS)).fit(train_rows, target_key)
    p2 = _RidgeLogitMulti(_FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS)).fit(train_rows, target_key)
    p3 = _RidgeLogitMulti(
        _FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS + SUBDELTA_IMPACT_COLS)
    ).fit(train_rows, target_key)
    p4 = _RidgeLogitMulti(
        _FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS + SUBDELTA_IMPACT_COLS + TEAMSTATE_COLS)
    ).fit(train_rows, target_key)
    return {
        "W2": w2_poisson,
        "P1": p1.predict_one,
        "P2": p2.predict_one,
        "P3": p3.predict_one,
        "P4": p4.predict_one,
    }


def nextgoal_predictors(train_rows: Sequence[dict], target_key: str = "next_goal_15") -> Dict[str, Callable]:
    """N0 base-rate + N1 hazard + N2 (+on-pitch impact) + N3 (+sub delta)."""
    base = float(np.mean([int(r[target_key]) for r in train_rows])) if train_rows else 0.0
    n1 = _RidgeLogitBin(_FeatureSpace(TEAMSTATE_COLS, with_w2_anchor=False)).fit(train_rows, target_key)
    n2 = _RidgeLogitBin(
        _FeatureSpace(TEAMSTATE_COLS + ONPITCH_IMPACT_COLS, with_w2_anchor=False)
    ).fit(train_rows, target_key)
    n3 = _RidgeLogitBin(
        _FeatureSpace(TEAMSTATE_COLS + ONPITCH_IMPACT_COLS + SUBDELTA_IMPACT_COLS, with_w2_anchor=False)
    ).fit(train_rows, target_key)
    return {
        "N0": lambda r: base,
        "N1": n1.predict_one,
        "N2": n2.predict_one,
        "N3": n3.predict_one,
    }


DISCIPLINE_POSITIVE_GATE = 150


def discipline_predictors(train_rows: Sequence[dict], target_key: str = "discipline_event") -> Dict:
    """C0 base-rate; C1 (+discipline history) gated on >=150 positive train examples.

    Returns {"predictors": {name: fn}, "n_positives": int, "C1_gate_open": bool, "gate_threshold": 150}.
    When the gate is closed only C0 is returned, with C1 marked SKIPPED (preregistered)."""
    pos = int(sum(int(r.get(target_key, 0)) for r in train_rows))
    base = float(np.mean([int(r.get(target_key, 0)) for r in train_rows])) if train_rows else 0.0
    preds: Dict[str, Callable] = {"C0": (lambda r: base)}
    gate_open = pos >= DISCIPLINE_POSITIVE_GATE
    if gate_open:
        c1 = _RidgeLogitBin(
            _FeatureSpace(DISCIPLINE_HIST_COLS, with_w2_anchor=False)
        ).fit(train_rows, target_key)
        preds["C1"] = c1.predict_one
    return {"predictors": preds, "n_positives": pos, "C1_gate_open": gate_open,
            "gate_threshold": DISCIPLINE_POSITIVE_GATE,
            "C1_status": "fit" if gate_open else "SKIPPED_below_gate"}


def xg_fusion_predictors(train_rows: Sequence[dict], target_key: str = "target_wdl") -> Dict[str, Callable]:
    """xG-fusion W/D/L families on the xG-matched subset. Callers should pass the xG-matched subset as
    train_rows; X0 is the W2 reference, X1 adds xG-event-state, X2 adds player-impact, X3 adds both."""
    x1 = _RidgeLogitMulti(_FeatureSpace(XG_EVENT_COLS)).fit(train_rows, target_key)
    x2 = _RidgeLogitMulti(
        _FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS)
    ).fit(train_rows, target_key)
    x3 = _RidgeLogitMulti(
        _FeatureSpace(XG_EVENT_COLS + PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS)
    ).fit(train_rows, target_key)
    return {
        "X0": w2_poisson,
        "X1": x1.predict_one,
        "X2": x2.predict_one,
        "X3": x3.predict_one,
    }


__all__ = [
    "MODEL_VERSION", "W2_BASE", "WDL",
    "w2_poisson", "wdl_predictors", "nextgoal_predictors",
    "discipline_predictors", "xg_fusion_predictors",
    "DISCIPLINE_POSITIVE_GATE",
    "PREMATCH_IMPACT_COLS", "ONPITCH_IMPACT_COLS", "SUBDELTA_IMPACT_COLS",
    "TEAMSTATE_COLS", "XG_EVENT_COLS", "DISCIPLINE_HIST_COLS",
]
