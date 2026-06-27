"""Dynamic in-play MODEL FAMILIES (Phase 4). research_only / experimental / not_runtime_approved /
not_trade_eligible / not_live_eligible.

Transparent, regularized, preregistered model classes ONLY. No neural nets / transformers / LLM /
unrestricted hyperparameter search. Every fit, every scaler, every calibrator is learned INSIDE the
training rows handed to ``fit`` and frozen for prediction -- there is no global state and nothing here
ever consults a test row. The regularization strength is chosen by a small fixed grid + internal
deterministic CV on the TRAIN rows only.

Canonical model IDs implemented here (use verbatim; NEVER M1-M5):

  W/D/L (ordered 3-class multinomial logistic, score-state aware):
    research.wdl.static_b1_anchor_r0        -- r0 reference: training base-rate W/D/L (static anchor).
    research.wdl.time_score_baseline_r1     -- r1 reference: minute + current score-state logistic.
    research.wdl.remaining_time_poisson_r2  -- r2 reference: remaining-time Poisson on current score diff
                                               (parameter-free; reimplemented, NOT the frozen prospective M2).
    research.wdl.player_starting_xi_p1       -- p1: r2-logit anchor + PRE-MATCH starting-XI impact diff.
    research.wdl.player_on_pitch_p2          -- p2: p1 + CURRENT on-pitch impact diff.
    research.wdl.player_substitution_delta_p3-- p3: p2 + substitution-delta history.
    research.wdl.player_composition_p4       -- p4: p3 + composition / continuity proxies.
    research.wdl.player_team_state_p5        -- p5: p4 + full team-state (cards / sendings-off / subs).
    research.wdl.xg_event_state_x1           -- x1: r2-anchor + xG event-state (xG-matched subset only).
    research.wdl.xg_player_state_x2          -- x2: r2-anchor + player-impact (xG-matched subset only).
    research.wdl.xg_calibrated_hybrid_x3     -- x3: fixed-form calibrated blend of r2 + x1 + x2,
                                               isotonic/Platt fit inside-training-only.

  Next goal (binary P(regulation goal in next 15'), regularized discrete-time hazard):
    research.next_goal.time_score_n0
    research.next_goal.time_score_cards_subs_n1
    research.next_goal.player_on_pitch_n2
    research.next_goal.substitution_delta_n3
    research.next_goal.xg_player_fusion_n4

  Discipline (binary discrete-time hazard; C1/C2 gated on >=150 positives):
    research.discipline.yellow_hazard_c0
    research.discipline.sending_off_hazard_c1
    research.discipline.player_team_prior_c2

Graceful degradation: each model declares the feature columns it wants. A row missing a wanted value is
imputed with the TRAIN mean and flagged with a companion ``<col>__unknown`` indicator (1.0 when imputed),
so a row with no information reduces to the anchor rather than crashing. Imputation means are TRAIN-only.

Determinism: fixed feature order; sklearn solvers seeded (random_state=0); fixed C grid; deterministic
internal CV folds; no RNG at predict time. If scikit-learn is importable it is used; otherwise the linear
models fall back to a numpy IRLS / closed-form ridge fitter (also deterministic).
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

MODEL_VERSION = "dynamic_models_v1"
WDL = ["H", "D", "A"]
R2_BASE = 1.35  # goals per team per 90' (remaining-time Poisson reference; reimplemented, NOT imported from M2)

# ----------------------------------------------------------------------------------------------------
# scikit-learn availability probe (preferred); numpy IRLS/ridge fallback otherwise.
# ----------------------------------------------------------------------------------------------------
try:  # pragma: no cover - environment dependent
    from sklearn.linear_model import LogisticRegression as _SkLogit  # noqa: F401
    HAVE_SKLEARN = True
except Exception:  # pragma: no cover
    HAVE_SKLEARN = False

# ----------------------------------------------------------------------------------------------------
# Per-row feature column names. Models degrade gracefully when these are absent on a row.
# (These mirror the snapshot dicts from scripts/research_jobs/_common.regulation_snapshots, optionally
#  augmented with player-impact columns by player_history and xG columns from the xG snapshot join.)
# ----------------------------------------------------------------------------------------------------
SCORE_STATE_COLS = ["score_diff", "minute", "remaining"]
TEAMSTATE_COLS = ["score_diff", "card_diff", "so_diff", "subs_diff", "player_count_diff", "remaining"]
PREMATCH_IMPACT_COLS = ["prematch_impact_diff", "prematch_impact_uncertainty", "prematch_impact_coverage"]
ONPITCH_IMPACT_COLS = ["onpitch_impact_diff"]
SUBDELTA_IMPACT_COLS = ["sub_impact_delta"]
COMPOSITION_COLS = ["lineup_continuity_diff", "n_starters_home"]
XG_EVENT_COLS = ["cum_xg_diff", "roll5_xg_diff", "roll10_xg_diff", "xg_momentum",
                 "shot_count_diff", "shot_on_target_diff", "time_since_last_shot",
                 "time_since_last_major_chance"]
DISCIPLINE_HIST_COLS = ["team_card_rate_prior", "opp_card_rate_prior", "subs_diff", "score_diff"]
NEXTGOAL_BASE_COLS = ["minute", "score_diff", "remaining"]


def _norm(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(d.values()) or 1.0
    return {k: v / s for k, v in d.items()}


# ====================================================================================================
# r2 remaining-time Poisson reference (reimplemented; parameter-free, no fitting, no leakage)
# ====================================================================================================
def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def r2_remaining_time_poisson(row: dict) -> Dict[str, float]:
    """P(final H/D/A) from the current regulation score diff + remaining minutes. Parameter-free."""
    rem = max(0, int(round(float(row.get("remaining", 0)))))
    lam = R2_BASE * rem / 90.0
    diff0 = int(round(float(row.get("score_diff", 0))))
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


def _r2_logit_anchor(row: dict, eps: float = 1e-6) -> List[float]:
    """r2 probabilities as two log-odds offsets (H vs D, A vs D): a leakage-free anchor feature."""
    p = r2_remaining_time_poisson(row)
    pd_ = max(eps, p["D"])
    return [math.log(max(eps, p["H"]) / pd_), math.log(max(eps, p["A"]) / pd_)]


# ====================================================================================================
# Feature assembly with graceful unknown handling (impute on TRAIN means + unknown indicator)
# ====================================================================================================
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


class FeatureSpace:
    """Fixed-order feature builder. For each requested column it emits the (imputed) value and a companion
    ``<col>__unknown`` indicator. Imputation means are learned on TRAIN only and frozen for predict."""

    def __init__(self, cols: Sequence[str], with_r2_anchor: bool = True):
        self.cols = list(cols)
        self.with_r2_anchor = with_r2_anchor
        self.means: Dict[str, float] = {}

    @property
    def names(self) -> List[str]:
        out: List[str] = []
        if self.with_r2_anchor:
            out += ["r2_logit_H", "r2_logit_A"]
        for c in self.cols:
            out += [c, c + "__unknown"]
        return out

    def fit(self, train_rows: Sequence[dict]) -> "FeatureSpace":
        for c in self.cols:
            vals = [v for v in (_raw_value(r, c) for r in train_rows) if v is not None]
            self.means[c] = float(np.mean(vals)) if vals else 0.0
        return self

    def row_vector(self, row: dict) -> List[float]:
        vec: List[float] = []
        if self.with_r2_anchor:
            vec += _r2_logit_anchor(row)
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


# ====================================================================================================
# numpy fallback fitters (deterministic) used when scikit-learn is unavailable.
# Ridge-penalized multinomial / binary logistic via Newton-IRLS. Penalty applied to non-intercept weights.
# ====================================================================================================
def _np_softmax(Z: np.ndarray) -> np.ndarray:
    Z = Z - Z.max(axis=1, keepdims=True)
    e = np.exp(Z)
    return e / e.sum(axis=1, keepdims=True)


def _np_fit_multinomial(X: np.ndarray, y_idx: np.ndarray, n_classes: int, C: float,
                        iters: int = 60) -> np.ndarray:
    """Ridge multinomial logistic by damped Newton / gradient descent. lam = 1/C on non-bias weights.
    Returns W of shape (n_features+1, n_classes) (last reference class fixed at 0)."""
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    lam = 1.0 / max(C, 1e-6)
    W = np.zeros((d + 1, n_classes))
    Y = np.zeros((n, n_classes))
    Y[np.arange(n), y_idx] = 1.0
    pen = np.ones(d + 1) * lam
    pen[-1] = 0.0  # no penalty on intercept
    lr = 1.0
    for _ in range(iters):
        P = _np_softmax(Xb @ W)
        G = Xb.T @ (P - Y) + (pen[:, None] * W)
        # diagonal-ish Hessian scaling for stability (deterministic, no line search RNG)
        H = (Xb * Xb).sum(axis=0)[:, None] * 0.25 + pen[:, None] + 1e-6
        W = W - lr * G / H
    return W


def _np_predict_multinomial(W: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    return _np_softmax(Xb @ W)


def _np_fit_binary(X: np.ndarray, y: np.ndarray, C: float, iters: int = 60) -> np.ndarray:
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    lam = 1.0 / max(C, 1e-6)
    w = np.zeros(d + 1)
    pen = np.ones(d + 1) * lam
    pen[-1] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(Xb @ w)))
        g = Xb.T @ (p - y) + pen * w
        h = (Xb * Xb * (p * (1 - p))[:, None]).sum(axis=0) + pen + 1e-6
        w = w - g / h
    return w


def _np_predict_binary(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    return 1.0 / (1.0 + np.exp(-(Xb @ w)))


# ====================================================================================================
# Regularized fitters. Regularization strength chosen by internal deterministic CV on TRAIN ONLY.
# ====================================================================================================
_C_GRID = [0.03, 0.1, 0.3, 1.0, 3.0]


def _internal_folds(n: int, k: int = 3, seed: int = 0) -> List[np.ndarray]:
    """Deterministic k-fold index split (seeded RNG; no global RNG state mutation)."""
    idx = np.arange(n)
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    k = max(2, min(k, n)) if n >= 2 else 1
    return [idx[i::k] for i in range(k)]


def _safe_logloss_multi(P: np.ndarray, y_idx: np.ndarray, eps: float = 1e-12) -> float:
    tot = 0.0
    for j in range(len(y_idx)):
        tot += -math.log(max(eps, float(P[j][y_idx[j]])))
    return tot / max(1, len(y_idx))


def _base_rate(train_rows: Sequence[dict], target_key: str, classes) -> Dict[str, float]:
    c = {k: 0.0 for k in classes}
    for r in train_rows:
        t = r.get(target_key)
        if t in c:
            c[t] += 1.0
    return _norm({k: v + 1e-6 for k, v in c.items()})


class RidgeLogitMulti:
    """Ridge multinomial logistic (ordered W/D/L). C selected by internal CV (mean val log-loss) on train.
    Uses scikit-learn if available, else a deterministic numpy IRLS fallback. Standardized inside-train."""

    def __init__(self, space: FeatureSpace):
        self.space = space
        self.model = None          # sklearn estimator OR numpy weight matrix
        self.backend = "sklearn" if HAVE_SKLEARN else "numpy"
        self.scaler_mean = None
        self.scaler_std = None
        self.classes_: List[str] = []
        self.selected_C: Optional[float] = None
        self.fallback: Optional[Dict[str, float]] = None

    def _standardize_fit(self, X: np.ndarray):
        self.scaler_mean = X.mean(axis=0)
        self.scaler_std = X.std(axis=0)
        self.scaler_std[self.scaler_std == 0] = 1.0

    def _standardize(self, X: np.ndarray) -> np.ndarray:
        return (X - self.scaler_mean) / self.scaler_std

    def _fit_backend(self, Xs, y_idx, C):
        if self.backend == "sklearn":
            from sklearn.linear_model import LogisticRegression
            m = LogisticRegression(C=C, penalty="l2", solver="lbfgs", max_iter=2000, random_state=0)
            m.fit(Xs, y_idx)
            return m
        return _np_fit_multinomial(Xs, y_idx, len(self.classes_), C)

    def _proba_backend(self, model, Xs) -> np.ndarray:
        if self.backend == "sklearn":
            P = model.predict_proba(Xs)
            # reorder columns to self.classes_ order
            col = {int(c): i for i, c in enumerate(model.classes_)}
            return np.column_stack([P[:, col[i]] for i in range(len(self.classes_))])
        return _np_predict_multinomial(model, Xs)

    def fit(self, train_rows: Sequence[dict], target_key: str = "target_wdl") -> "RidgeLogitMulti":
        self.space.fit(train_rows)
        X = self.space.matrix(train_rows)
        y = np.asarray([r[target_key] for r in train_rows])
        classes = [c for c in WDL if c in set(y.tolist())]
        self.classes_ = classes or WDL
        if len(classes) < 2 or len(y) < 6:
            self.fallback = _base_rate(train_rows, target_key, self.classes_)
            return self
        cls_idx = {c: i for i, c in enumerate(self.classes_)}
        y_idx = np.asarray([cls_idx[v] for v in y])
        self._standardize_fit(X)
        Xs = self._standardize(X)
        bestC, best = _C_GRID[0], math.inf
        folds = _internal_folds(len(y), k=min(3, max(2, len(y) // 4)))
        for C in _C_GRID:
            tot, cnt = 0.0, 0
            for fi in range(len(folds)):
                va = folds[fi]
                tr = np.concatenate([folds[j] for j in range(len(folds)) if j != fi]) if len(folds) > 1 else va
                if len(set(y_idx[tr].tolist())) < 2 or len(va) == 0:
                    continue
                m = self._fit_backend(Xs[tr], y_idx[tr], C)
                P = self._proba_backend(m, Xs[va])
                tot += _safe_logloss_multi(P, y_idx[va]) * len(va)
                cnt += len(va)
            if cnt and tot / cnt < best:
                best, bestC = tot / cnt, C
        self.model = self._fit_backend(Xs, y_idx, bestC)
        self.selected_C = bestC
        return self

    def predict_one(self, row: dict) -> Dict[str, float]:
        if self.model is None:
            return dict(self.fallback or _norm({k: 1.0 for k in WDL}))
        Xs = self._standardize(self.space.matrix([row]))
        p = self._proba_backend(self.model, Xs)[0]
        out = {k: 0.0 for k in WDL}
        for i, cls in enumerate(self.classes_):
            out[cls] = float(p[i])
        return _norm({k: out.get(k, 0.0) for k in WDL})


class RidgeLogitBin:
    """Ridge binary logistic discrete-time hazard. C selected by internal CV on train. sklearn or numpy."""

    def __init__(self, space: FeatureSpace):
        self.space = space
        self.model = None
        self.backend = "sklearn" if HAVE_SKLEARN else "numpy"
        self.scaler_mean = None
        self.scaler_std = None
        self.base = 0.5
        self.selected_C: Optional[float] = None

    def _standardize_fit(self, X):
        self.scaler_mean = X.mean(axis=0)
        self.scaler_std = X.std(axis=0)
        self.scaler_std[self.scaler_std == 0] = 1.0

    def _standardize(self, X):
        return (X - self.scaler_mean) / self.scaler_std

    def _fit_backend(self, Xs, y, C):
        if self.backend == "sklearn":
            from sklearn.linear_model import LogisticRegression
            return LogisticRegression(C=C, penalty="l2", solver="lbfgs", max_iter=2000,
                                      random_state=0).fit(Xs, y)
        return _np_fit_binary(Xs, y.astype(float), C)

    def _proba_backend(self, model, Xs) -> np.ndarray:
        if self.backend == "sklearn":
            return model.predict_proba(Xs)[:, 1]
        return _np_predict_binary(model, Xs)

    def fit(self, train_rows: Sequence[dict], target_key: str) -> "RidgeLogitBin":
        self.space.fit(train_rows)
        X = self.space.matrix(train_rows)
        y = np.asarray([int(r[target_key]) for r in train_rows])
        self.base = float(y.mean()) if len(y) else 0.5
        if len(set(y.tolist())) < 2 or len(y) < 6:
            self.model = None
            return self
        self._standardize_fit(X)
        Xs = self._standardize(X)
        bestC, best = _C_GRID[0], math.inf
        folds = _internal_folds(len(y), k=min(3, max(2, len(y) // 4)))
        for C in _C_GRID:
            tot, cnt = 0.0, 0
            for fi in range(len(folds)):
                va = folds[fi]
                tr = np.concatenate([folds[j] for j in range(len(folds)) if j != fi]) if len(folds) > 1 else va
                if len(set(y[tr].tolist())) < 2 or len(va) == 0:
                    continue
                m = self._fit_backend(Xs[tr], y[tr], C)
                p = np.clip(self._proba_backend(m, Xs[va]), 1e-9, 1 - 1e-9)
                ll = float(-np.mean(y[va] * np.log(p) + (1 - y[va]) * np.log(1 - p)))
                tot += ll * len(va)
                cnt += len(va)
            if cnt and tot / cnt < best:
                best, bestC = tot / cnt, C
        self.model = self._fit_backend(Xs, y, bestC)
        self.selected_C = bestC
        return self

    def predict_one(self, row: dict) -> float:
        if self.model is None:
            return float(self.base)
        Xs = self._standardize(self.space.matrix([row]))
        return float(np.clip(self._proba_backend(self.model, Xs)[0], 1e-9, 1 - 1e-9))


# ====================================================================================================
# Monotonic / Platt calibration -- fit INSIDE training only (used by the x3 fixed-form calibrated blend).
# ====================================================================================================
class IsotonicCalibrator:
    """Monotone (isotonic) probability calibrator for a single binary channel. Falls back to Platt
    (1-D logistic) when isotonic is unavailable. Fit on TRAIN (prob, label) pairs ONLY."""

    def __init__(self):
        self.kind = None
        self.iso = None
        self.platt = None  # (a, b) for sigmoid(a*logit(p)+b)

    def fit(self, p: np.ndarray, y: np.ndarray) -> "IsotonicCalibrator":
        p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
        y = np.asarray(y, dtype=float)
        if len(p) < 10 or len(set(y.tolist())) < 2:
            self.kind = "identity"
            return self
        if HAVE_SKLEARN:
            try:
                from sklearn.isotonic import IsotonicRegression
                self.iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p, y)
                self.kind = "isotonic"
                return self
            except Exception:
                pass
        # Platt fallback: logistic on logit(p)
        z = np.log(p / (1 - p)).reshape(-1, 1)
        if HAVE_SKLEARN:
            from sklearn.linear_model import LogisticRegression
            m = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000).fit(z, y)
            self.platt = (float(m.coef_[0][0]), float(m.intercept_[0]))
        else:
            w = _np_fit_binary(z, y, C=1e6)
            self.platt = (float(w[0]), float(w[1]))
        self.kind = "platt"
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
        if self.kind == "isotonic" and self.iso is not None:
            return np.clip(self.iso.predict(p), 1e-9, 1 - 1e-9)
        if self.kind == "platt" and self.platt is not None:
            a, b = self.platt
            z = np.log(p / (1 - p))
            return 1.0 / (1.0 + np.exp(-(a * z + b)))
        return p


class CalibratedBlend:
    """Fixed-form calibrated blend of several W/D/L predictors (x3 hybrid).

    The blend FORM is fixed and preregistered: per-class geometric pool of component probabilities with
    fixed equal log-weights, then per-class isotonic/Platt calibration fit INSIDE training only, then
    renormalize. No blend weight is tuned on the test rows; only the monotone calibrators are fit, and
    they are fit on the SAME training rows the components were fit on (so x3 never sees test labels)."""

    def __init__(self, components: List[Callable[[dict], Dict[str, float]]]):
        self.components = components
        self.cal: Dict[str, IsotonicCalibrator] = {}

    def _pool(self, row: dict) -> Dict[str, float]:
        eps = 1e-9
        logsum = {k: 0.0 for k in WDL}
        for fn in self.components:
            p = fn(row)
            for k in WDL:
                logsum[k] += math.log(max(eps, p.get(k, 0.0)))
        w = 1.0 / max(1, len(self.components))
        pooled = {k: math.exp(w * logsum[k]) for k in WDL}
        return _norm(pooled)

    def fit(self, train_rows: Sequence[dict], target_key: str = "target_wdl") -> "CalibratedBlend":
        pooled = [self._pool(r) for r in train_rows]
        y = [r[target_key] for r in train_rows]
        for k in WDL:
            pk = np.array([pp[k] for pp in pooled])
            yk = np.array([1.0 if t == k else 0.0 for t in y])
            self.cal[k] = IsotonicCalibrator().fit(pk, yk)
        return self

    def predict_one(self, row: dict) -> Dict[str, float]:
        pooled = self._pool(row)
        out = {}
        for k in WDL:
            c = self.cal.get(k)
            out[k] = float(c.transform(np.array([pooled[k]]))[0]) if c is not None else pooled[k]
        return _norm(out)


# ====================================================================================================
# r0 / r1 reference closures
# ====================================================================================================
def _r1_predictor(train_rows: Sequence[dict]) -> Callable[[dict], Dict[str, float]]:
    """r1: minute + current score-state multinomial logistic (no player/xG features)."""
    m = RidgeLogitMulti(FeatureSpace(SCORE_STATE_COLS, with_r2_anchor=False)).fit(train_rows, "target_wdl")
    return m.predict_one


# ====================================================================================================
# Public family factories. Each returns {canonical_id: predict(row)->probs|float}, fit on TRAIN only.
# ====================================================================================================
def wdl_predictors(train_rows: Sequence[dict], target_key: str = "target_wdl") -> Dict[str, Callable]:
    """W/D/L family: r0 (base rate), r1 (time+score logistic), r2 (remaining-time Poisson reference),
    p1..p5 (player-impact ladder)."""
    br = _base_rate(train_rows, target_key, WDL)
    r1 = _r1_predictor(train_rows)
    p1 = RidgeLogitMulti(FeatureSpace(PREMATCH_IMPACT_COLS)).fit(train_rows, target_key)
    p2 = RidgeLogitMulti(FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS)).fit(train_rows, target_key)
    p3 = RidgeLogitMulti(
        FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS + SUBDELTA_IMPACT_COLS)
    ).fit(train_rows, target_key)
    p4 = RidgeLogitMulti(
        FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS + SUBDELTA_IMPACT_COLS + COMPOSITION_COLS)
    ).fit(train_rows, target_key)
    p5 = RidgeLogitMulti(
        FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS + SUBDELTA_IMPACT_COLS
                     + COMPOSITION_COLS + TEAMSTATE_COLS)
    ).fit(train_rows, target_key)
    return {
        "research.wdl.static_b1_anchor_r0": lambda r: dict(br),
        "research.wdl.time_score_baseline_r1": r1,
        "research.wdl.remaining_time_poisson_r2": r2_remaining_time_poisson,
        "research.wdl.player_starting_xi_p1": p1.predict_one,
        "research.wdl.player_on_pitch_p2": p2.predict_one,
        "research.wdl.player_substitution_delta_p3": p3.predict_one,
        "research.wdl.player_composition_p4": p4.predict_one,
        "research.wdl.player_team_state_p5": p5.predict_one,
    }


def xg_wdl_predictors(train_rows: Sequence[dict], target_key: str = "target_wdl") -> Dict[str, Callable]:
    """xG-fusion W/D/L families (call with the xG-matched subset as train_rows):
    r2 reference + x1 (xG event-state) + x2 (player-impact) + x3 (calibrated blend of r2/x1/x2)."""
    x1 = RidgeLogitMulti(FeatureSpace(XG_EVENT_COLS)).fit(train_rows, target_key)
    x2 = RidgeLogitMulti(FeatureSpace(PREMATCH_IMPACT_COLS + ONPITCH_IMPACT_COLS)).fit(train_rows, target_key)
    x3 = CalibratedBlend([r2_remaining_time_poisson, x1.predict_one, x2.predict_one]).fit(train_rows, target_key)
    return {
        "research.wdl.remaining_time_poisson_r2": r2_remaining_time_poisson,
        "research.wdl.xg_event_state_x1": x1.predict_one,
        "research.wdl.xg_player_state_x2": x2.predict_one,
        "research.wdl.xg_calibrated_hybrid_x3": x3.predict_one,
    }


def nextgoal_predictors(train_rows: Sequence[dict], target_key: str = "next_goal_15") -> Dict[str, Callable]:
    """Next-goal discrete-time hazard family: n0 base rate, n1 (+cards/subs), n2 (+on-pitch impact),
    n3 (+sub delta), n4 (+xG player fusion)."""
    base = float(np.mean([int(r[target_key]) for r in train_rows])) if train_rows else 0.0
    n1 = RidgeLogitBin(FeatureSpace(TEAMSTATE_COLS, with_r2_anchor=False)).fit(train_rows, target_key)
    n2 = RidgeLogitBin(
        FeatureSpace(TEAMSTATE_COLS + ONPITCH_IMPACT_COLS, with_r2_anchor=False)
    ).fit(train_rows, target_key)
    n3 = RidgeLogitBin(
        FeatureSpace(TEAMSTATE_COLS + ONPITCH_IMPACT_COLS + SUBDELTA_IMPACT_COLS, with_r2_anchor=False)
    ).fit(train_rows, target_key)
    n4 = RidgeLogitBin(
        FeatureSpace(TEAMSTATE_COLS + ONPITCH_IMPACT_COLS + XG_EVENT_COLS, with_r2_anchor=False)
    ).fit(train_rows, target_key)
    return {
        "research.next_goal.time_score_n0": lambda r: base,
        "research.next_goal.time_score_cards_subs_n1": n1.predict_one,
        "research.next_goal.player_on_pitch_n2": n2.predict_one,
        "research.next_goal.substitution_delta_n3": n3.predict_one,
        "research.next_goal.xg_player_fusion_n4": n4.predict_one,
    }


DISCIPLINE_POSITIVE_GATE = 150


def discipline_predictors(train_rows: Sequence[dict], target_key: str = "discipline_event") -> Dict:
    """Discipline discrete-time hazard: c0 yellow base rate; c1 sending-off hazard, c2 (+player/team prior)
    -- c1/c2 gated on >=150 positive train examples (preregistered).

    Returns {"predictors": {id: fn}, "n_positives": int, "gate_open": bool, "gate_threshold": 150}."""
    pos = int(sum(int(r.get(target_key, 0)) for r in train_rows))
    base = float(np.mean([int(r.get(target_key, 0)) for r in train_rows])) if train_rows else 0.0
    preds: Dict[str, Callable] = {"research.discipline.yellow_hazard_c0": (lambda r: base)}
    gate_open = pos >= DISCIPLINE_POSITIVE_GATE
    if gate_open:
        c1 = RidgeLogitBin(
            FeatureSpace(TEAMSTATE_COLS, with_r2_anchor=False)
        ).fit(train_rows, target_key)
        c2 = RidgeLogitBin(
            FeatureSpace(DISCIPLINE_HIST_COLS, with_r2_anchor=False)
        ).fit(train_rows, target_key)
        preds["research.discipline.sending_off_hazard_c1"] = c1.predict_one
        preds["research.discipline.player_team_prior_c2"] = c2.predict_one
    return {"predictors": preds, "n_positives": pos, "gate_open": gate_open,
            "gate_threshold": DISCIPLINE_POSITIVE_GATE,
            "gated_status": "fit" if gate_open else "SKIPPED_below_gate"}


__all__ = [
    "MODEL_VERSION", "R2_BASE", "WDL", "HAVE_SKLEARN",
    "r2_remaining_time_poisson", "FeatureSpace", "RidgeLogitMulti", "RidgeLogitBin",
    "IsotonicCalibrator", "CalibratedBlend",
    "wdl_predictors", "xg_wdl_predictors", "nextgoal_predictors", "discipline_predictors",
    "DISCIPLINE_POSITIVE_GATE",
    "SCORE_STATE_COLS", "TEAMSTATE_COLS", "PREMATCH_IMPACT_COLS", "ONPITCH_IMPACT_COLS",
    "SUBDELTA_IMPACT_COLS", "COMPOSITION_COLS", "XG_EVENT_COLS", "DISCIPLINE_HIST_COLS",
]
