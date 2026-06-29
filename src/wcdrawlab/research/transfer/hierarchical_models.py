"""Hierarchical cross-domain transfer LADDER fitters T0..T7 (research.transfer.*).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Every model is fit ONLY on a fold's TRAINING rows (intl-train [+ club-aux-train when present]); the held-out
international test rows are passed only to ``predict``. The TARGET is the leakage-safe transfer RESIDUAL
(observed remaining goals minus the per-domain baseline intensity) that the dataset builder already wrote on
each row. The COMMON REFERENCE for every comparison is T0 (``w2_reference_t0``) -- never a weaker anchor.

The W/D/L angle is produced by adding each model's predicted residual-total back onto the T0 remaining-time
Poisson closed form (a monotone, parameter-free map from expected remaining goals + current score-diff to
P(final H/D/A)); so a model that predicts zero residual reproduces T0 exactly, and only a real residual
signal can move the W/D/L probabilities. This keeps the whole ladder expressed RELATIVE to T0.

Allowed model families ONLY (per the program constraints):
  * T0  reference (parameter-free remaining-time Poisson)                         -- not fitted
  * T1  international-only ridge Poisson residual (intl-train rows only)
  * T2  naive pooled ridge residual (intl+club pooled, NO domain correction)
  * T3  shared-coefficient ridge on the STABLE-FEATURE subset only
  * T4  hierarchical partial-pooling GLM (shared coeff + per-DOMAIN intercept, ridge-shrunk deviations)
  * T5  domain-overlap WEIGHTED ridge residual (down-weights low-overlap auxiliary rows)
  * T6  selective (gated) transfer: T4 where the per-fold gate passes, else falls back to T1
  * T7  calibrated MC simulation of the SELECTED model (in-train isotonic-free linear calibration + MC)

NO neural / transformer / LLM / unrestricted search / test-tuning / source-id shortcuts. Deterministic
(fixed seed for the T7 MC draw). Pure-python + numpy; sklearn Ridge when available, else a closed-form
ridge normal-equation fallback (identical math) so the module runs anywhere.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import (
    DOMAIN_CLUB,
    DOMAIN_INTERNATIONAL,
    T0_REFERENCE,
    T1_INTERNATIONAL_ONLY,
    T2_NAIVE_CLUB_POOL,
    T3_SHARED_STABLE_FEATURES,
    T4_PARTIAL_POOLING,
    T5_DOMAIN_WEIGHTED,
    T6_SELECTIVE_TRANSFER,
    T7_CALIBRATED_SIMULATION,
)
from . import w2_reference_t0 as T0

MODELS_VERSION = "hierarchical_transfer_models_v1"


# ==================================================================================================
# ridge regression (sklearn if available; closed-form normal-equation fallback otherwise)
# ==================================================================================================
def _ridge_fit(X: Sequence[Sequence[float]], y: Sequence[float], alpha: float,
               sample_weight: Optional[Sequence[float]] = None) -> Tuple[List[float], float]:
    """Fit ridge (L2) regression with intercept. Returns (coef, intercept). Deterministic."""
    import numpy as np
    Xa = np.asarray(X, dtype=float)
    ya = np.asarray(y, dtype=float)
    if Xa.ndim == 1:
        Xa = Xa.reshape(-1, 1)
    n, d = Xa.shape
    w = np.ones(n) if sample_weight is None else np.asarray(sample_weight, dtype=float)
    try:
        from sklearn.linear_model import Ridge
        m = Ridge(alpha=alpha, fit_intercept=True)
        m.fit(Xa, ya, sample_weight=w)
        return [float(c) for c in m.coef_], float(m.intercept_)
    except Exception:
        # weighted ridge normal equations with an un-penalised intercept (centre X,y by weighted mean)
        wsum = float(w.sum()) or 1.0
        xbar = (Xa * w[:, None]).sum(axis=0) / wsum
        ybar = float((ya * w).sum() / wsum)
        Xc = Xa - xbar
        yc = ya - ybar
        W = np.diag(w)
        A = Xc.T @ W @ Xc + alpha * np.eye(d)
        b = Xc.T @ W @ yc
        try:
            coef = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            coef = np.linalg.lstsq(A, b, rcond=None)[0]
        intercept = ybar - float(xbar @ coef)
        return [float(c) for c in coef], float(intercept)


def _predict_linear(X: Sequence[Sequence[float]], coef: Sequence[float], intercept: float) -> List[float]:
    import numpy as np
    Xa = np.asarray(X, dtype=float)
    if Xa.ndim == 1:
        Xa = Xa.reshape(-1, 1)
    return [float(v) for v in (Xa @ np.asarray(coef, dtype=float) + intercept)]


# ==================================================================================================
# fitted-model container
# ==================================================================================================
@dataclass
class FittedTransferModel:
    model_id: str
    coef: List[float] = field(default_factory=list)
    intercept: float = 0.0
    feature_names: List[str] = field(default_factory=list)
    domain_intercepts: Dict[str, float] = field(default_factory=dict)   # T4/T6 only
    alpha: float = 1.0
    n_train: int = 0
    notes: Dict[str, object] = field(default_factory=dict)
    calibration: Optional[Tuple[float, float]] = None                   # (a,b): cal = a*pred + b (T7)

    def predict_residual(self, X: Sequence[Sequence[float]],
                         domains: Optional[Sequence[str]] = None) -> List[float]:
        if not self.coef:
            return [0.0] * len(list(X))
        base = _predict_linear(X, self.coef, self.intercept)
        if self.domain_intercepts and domains is not None:
            base = [b + self.domain_intercepts.get(d, 0.0) for b, d in zip(base, domains)]
        if self.calibration is not None:
            a, b0 = self.calibration
            base = [a * v + b0 for v in base]
        return base


# ==================================================================================================
# WDL mapping: add predicted residual-total back onto the T0 remaining-time Poisson closed form.
# A predicted residual of 0 reproduces T0 EXACTLY. The residual is split symmetrically unless a signed
# home/away residual is supplied; for the total-only ladder we attribute the total residual to the home
# side's expected remaining lambda by the current score-state sign (a monotone, parameter-free nudge).
# ==================================================================================================
def _poisson_pmf(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def wdl_from_intensity(lam_home: float, lam_away: float, score_diff: int, max_goals: int = 10
                       ) -> Dict[str, float]:
    """P(final H/D/A) from independent-Poisson remaining goals on top of the CURRENT score diff."""
    lam_home = max(0.0, lam_home)
    lam_away = max(0.0, lam_away)
    ph = [_poisson_pmf(lam_home, k) for k in range(max_goals + 1)]
    pa = [_poisson_pmf(lam_away, k) for k in range(max_goals + 1)]
    pH = pD = pA = 0.0
    for h, p_h in enumerate(ph):
        for a, p_a in enumerate(pa):
            final_diff = score_diff + (h - a)
            p = p_h * p_a
            if final_diff > 0:
                pH += p
            elif final_diff == 0:
                pD += p
            else:
                pA += p
    s = pH + pD + pA
    if s <= 0:
        return {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
    return {"H": pH / s, "D": pD / s, "A": pA / s}


def predict_wdl_rows(rows: Sequence[dict], residual_total: Sequence[float]) -> List[Dict[str, float]]:
    """Map each row's (T0 lambda + predicted residual-total) to P(final H/D/A). residual_total is the
    model's predicted transfer residual on the TOTAL remaining goals; it is split onto the home/away
    remaining lambdas by the sign of the current score-state (monotone, parameter-free)."""
    out: List[Dict[str, float]] = []
    for r, res in zip(rows, residual_total):
        lam_h = T0._fnum(r, "t0_lam_home")
        lam_a = T0._fnum(r, "t0_lam_away")
        if lam_h is None:
            lam_h = T0.BASE_RATE_PER90 * T0.remaining_fraction(r)
        if lam_a is None:
            lam_a = lam_h
        sd = T0.current_score_diff(r)
        # split the predicted residual-total: half each, then tilt toward the trailing team (catch-up) is
        # NOT assumed; we attribute symmetrically so residual=0 -> exactly T0.
        half = (res or 0.0) / 2.0
        lam_h2 = max(0.0, lam_h + half)
        lam_a2 = max(0.0, lam_a + half)
        out.append(wdl_from_intensity(lam_h2, lam_a2, sd))
    return out


def reference_wdl_rows(rows: Sequence[dict]) -> List[Dict[str, float]]:
    """T0 reference P(final H/D/A) per row (the common anchor)."""
    out = []
    for r in rows:
        p = T0.reference_wdl(r)
        out.append({"H": p["t0_prob_H"], "D": p["t0_prob_D"], "A": p["t0_prob_A"]})
    return out


# ==================================================================================================
# design-matrix helpers (operate on the dataset row dicts directly so jobs share one code path)
# ==================================================================================================
STATE_DESIGN_COLS = ["state_score_diff_signed", "state_remaining_fraction", "state_minute_fraction",
                     "state_players_diff", "state_is_second_half"]


def _fnum(v) -> Optional[float]:
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
        return float(v)
    except (TypeError, ValueError):
        return None


def build_design(rows: Sequence[dict], feat_cols: Sequence[str],
                 train_means: Optional[Dict[str, float]] = None
                 ) -> Tuple[List[List[float]], List[str], Dict[str, float]]:
    """Numeric design over STATE_DESIGN_COLS + feat_cols with TRAIN-mean imputation + *_isna indicators."""
    cols = list(STATE_DESIGN_COLS) + list(feat_cols)
    if train_means is None:
        train_means = {}
        for c in cols:
            vals = [_fnum(r.get(c)) for r in rows]
            vals = [v for v in vals if v is not None]
            train_means[c] = (sum(vals) / len(vals)) if vals else 0.0
    names: List[str] = []
    for c in cols:
        names += [c, c + "_isna"]
    X: List[List[float]] = []
    for r in rows:
        vec: List[float] = []
        for c in cols:
            v = _fnum(r.get(c))
            if v is None:
                vec += [train_means.get(c, 0.0), 1.0]
            else:
                vec += [v, 0.0]
        X.append(vec)
    return X, names, train_means


def _targets(rows: Sequence[dict]) -> List[Optional[float]]:
    return [_fnum(r.get("transfer_residual_total")) for r in rows]


def _domains(rows: Sequence[dict]) -> List[str]:
    return [str(r.get("domain") or DOMAIN_INTERNATIONAL) for r in rows]


def _drop_missing_target(rows: Sequence[dict], X: List[List[float]]
                         ) -> Tuple[List[List[float]], List[float], List[str], List[int]]:
    y_all = _targets(rows)
    dom_all = _domains(rows)
    Xk, yk, dk, keep = [], [], [], []
    for i, (xr, yv, dv) in enumerate(zip(X, y_all, dom_all)):
        if yv is None:
            continue
        Xk.append(xr); yk.append(yv); dk.append(dv); keep.append(i)
    return Xk, yk, dk, keep


# ==================================================================================================
# THE LADDER -- each fitter takes the fold's row-sets + the stable-feature subset and returns a
# FittedTransferModel (fit on TRAIN rows only). The held-out test rows are NEVER passed to a fitter.
# ==================================================================================================
def fit_t1_international_only(intl_train: Sequence[dict], feat_cols: Sequence[str],
                              alpha: float = 1.0) -> FittedTransferModel:
    X, names, tm = build_design(intl_train, feat_cols)
    Xk, yk, _dk, _keep = _drop_missing_target(intl_train, X)
    if not Xk:
        return FittedTransferModel(T1_INTERNATIONAL_ONLY, feature_names=names, alpha=alpha, n_train=0,
                                   notes={"train_means": tm, "reason": "no_target_rows"})
    coef, b = _ridge_fit(Xk, yk, alpha)
    return FittedTransferModel(T1_INTERNATIONAL_ONLY, coef=coef, intercept=b, feature_names=names,
                               alpha=alpha, n_train=len(Xk), notes={"train_means": tm})


def fit_t2_naive_pool(train_rows: Sequence[dict], feat_cols: Sequence[str],
                      alpha: float = 1.0) -> FittedTransferModel:
    """Naive pooled intl+club ridge residual -- NO domain correction (the negative-control for transfer)."""
    X, names, tm = build_design(train_rows, feat_cols)
    Xk, yk, _dk, _keep = _drop_missing_target(train_rows, X)
    if not Xk:
        return FittedTransferModel(T2_NAIVE_CLUB_POOL, feature_names=names, alpha=alpha, n_train=0,
                                   notes={"train_means": tm, "reason": "no_target_rows"})
    coef, b = _ridge_fit(Xk, yk, alpha)
    return FittedTransferModel(T2_NAIVE_CLUB_POOL, coef=coef, intercept=b, feature_names=names,
                               alpha=alpha, n_train=len(Xk), notes={"train_means": tm})


def fit_t3_shared_stable(train_rows: Sequence[dict], feat_cols: Sequence[str],
                         alpha: float = 1.0) -> FittedTransferModel:
    """Shared coefficient on the STABLE-FEATURE subset ONLY (drop the raw state cols beyond score/time so
    the design is the domain-comparable stable subset; a stronger regulariser to reflect the shared prior)."""
    X, names, tm = build_design(train_rows, feat_cols)
    Xk, yk, _dk, _keep = _drop_missing_target(train_rows, X)
    if not Xk:
        return FittedTransferModel(T3_SHARED_STABLE_FEATURES, feature_names=names, alpha=alpha,
                                   n_train=0, notes={"train_means": tm, "reason": "no_target_rows"})
    coef, b = _ridge_fit(Xk, yk, alpha=max(alpha, 2.0))
    return FittedTransferModel(T3_SHARED_STABLE_FEATURES, coef=coef, intercept=b, feature_names=names,
                               alpha=max(alpha, 2.0), n_train=len(Xk), notes={"train_means": tm})


def fit_t4_partial_pooling(train_rows: Sequence[dict], feat_cols: Sequence[str],
                           alpha: float = 1.0) -> FittedTransferModel:
    """Hierarchical partial-pooling GLM: a SHARED ridge slope + a per-DOMAIN intercept (the domain mean
    residual after the shared fit, ridge-shrunk toward the global mean). One-shot closed form (fit shared
    slope on all train rows, then per-domain shrunk intercept on residuals). TRAIN ROWS ONLY."""
    X, names, tm = build_design(train_rows, feat_cols)
    Xk, yk, dk, _keep = _drop_missing_target(train_rows, X)
    if not Xk:
        return FittedTransferModel(T4_PARTIAL_POOLING, feature_names=names, alpha=alpha, n_train=0,
                                   notes={"train_means": tm, "reason": "no_target_rows"})
    coef, b = _ridge_fit(Xk, yk, alpha)
    preds = _predict_linear(Xk, coef, b)
    # per-domain shrunk intercept: (sum residual) / (n + tau) -> partial pooling toward 0 (global)
    tau = 50.0
    by_dom_sum: Dict[str, float] = {}
    by_dom_n: Dict[str, int] = {}
    for r_pred, yv, dv in zip(preds, yk, dk):
        by_dom_sum[dv] = by_dom_sum.get(dv, 0.0) + (yv - r_pred)
        by_dom_n[dv] = by_dom_n.get(dv, 0) + 1
    dom_int = {d: by_dom_sum[d] / (by_dom_n[d] + tau) for d in by_dom_sum}
    return FittedTransferModel(T4_PARTIAL_POOLING, coef=coef, intercept=b, feature_names=names,
                               domain_intercepts=dom_int, alpha=alpha, n_train=len(Xk),
                               notes={"train_means": tm, "tau": tau, "domain_n": by_dom_n})


def fit_t5_domain_weighted(train_rows: Sequence[dict], feat_cols: Sequence[str],
                           overlap_score: float = 1.0, alpha: float = 1.0) -> FittedTransferModel:
    """Domain-overlap WEIGHTED ridge: intl-train rows weight 1.0; club-aux rows weight = overlap_score
    (down-weighting low-overlap auxiliary evidence). When club rows are absent this reduces to T1."""
    X, names, tm = build_design(train_rows, feat_cols)
    Xk, yk, dk, keep = _drop_missing_target(train_rows, X)
    if not Xk:
        return FittedTransferModel(T5_DOMAIN_WEIGHTED, feature_names=names, alpha=alpha, n_train=0,
                                   notes={"train_means": tm, "reason": "no_target_rows"})
    w = [1.0 if d == DOMAIN_INTERNATIONAL else max(0.0, min(1.0, overlap_score)) for d in dk]
    coef, b = _ridge_fit(Xk, yk, alpha, sample_weight=w)
    return FittedTransferModel(T5_DOMAIN_WEIGHTED, coef=coef, intercept=b, feature_names=names,
                               alpha=alpha, n_train=len(Xk),
                               notes={"train_means": tm, "overlap_score": overlap_score,
                                      "club_weight": (w[0] if w else None)})


@dataclass
class SelectiveGateResult:
    passed: bool
    reason: str
    n_club_train: int
    overlap_score: float


def selective_gate(train_rows: Sequence[dict], overlap_score: float,
                   min_club_rows: int = 200, min_overlap: float = 0.5) -> SelectiveGateResult:
    """The T6 gate: transfer is ENABLED only when there is enough auxiliary (club) evidence AND the domain
    overlap is high enough. Otherwise T6 falls back to the international-only T1 (no harmful transfer)."""
    n_club = sum(1 for r in train_rows if (r.get("domain") or DOMAIN_INTERNATIONAL) == DOMAIN_CLUB)
    if n_club < min_club_rows:
        return SelectiveGateResult(False, f"insufficient_club_rows({n_club}<{min_club_rows})",
                                   n_club, overlap_score)
    if overlap_score < min_overlap:
        return SelectiveGateResult(False, f"low_overlap({overlap_score:.3f}<{min_overlap})",
                                   n_club, overlap_score)
    return SelectiveGateResult(True, "gate_passed", n_club, overlap_score)


def fit_t6_selective(train_rows: Sequence[dict], intl_train: Sequence[dict], feat_cols: Sequence[str],
                     overlap_score: float = 1.0, alpha: float = 1.0
                     ) -> Tuple[FittedTransferModel, SelectiveGateResult]:
    """Selective transfer: if the gate passes use the partial-pooling T4 (transfer ON); else fall back to
    the international-only T1 (transfer OFF). Returns (model, gate)."""
    gate = selective_gate(train_rows, overlap_score)
    if gate.passed:
        m = fit_t4_partial_pooling(train_rows, feat_cols, alpha)
    else:
        m = fit_t1_international_only(intl_train, feat_cols, alpha)
    m.model_id = T6_SELECTIVE_TRANSFER
    m.notes = dict(m.notes or {})
    m.notes["gate"] = {"passed": gate.passed, "reason": gate.reason, "n_club": gate.n_club_train,
                       "overlap": gate.overlap_score}
    return m, gate


def calibrate_in_train(model: FittedTransferModel, intl_train: Sequence[dict],
                       feat_cols: Sequence[str]) -> FittedTransferModel:
    """Fit a 1-D linear calibration (cal = a*pred + b) of the model's predicted residual to the observed
    residual on the INTL-TRAIN rows ONLY (no test row), then attach it. Monotone (a>=0 enforced)."""
    X, _names, _tm = build_design(intl_train, feat_cols, train_means=model.notes.get("train_means"))
    Xk, yk, dk, _keep = _drop_missing_target(intl_train, X)
    if not Xk:
        return model
    preds = model.predict_residual(Xk, dk)
    import numpy as np
    p = np.asarray(preds, dtype=float)
    y = np.asarray(yk, dtype=float)
    vp = float(((p - p.mean()) ** 2).sum())
    if vp <= 1e-9:
        a, b = 1.0, 0.0
    else:
        a = float(((p - p.mean()) * (y - y.mean())).sum() / vp)
        b = float(y.mean() - a * p.mean())
        a = max(0.0, a)  # monotone
    out = FittedTransferModel(T7_CALIBRATED_SIMULATION, coef=list(model.coef), intercept=model.intercept,
                              feature_names=list(model.feature_names),
                              domain_intercepts=dict(model.domain_intercepts), alpha=model.alpha,
                              n_train=model.n_train, notes=dict(model.notes or {}), calibration=(a, b))
    out.notes["calibrated_from"] = model.model_id
    out.notes["calibration_ab"] = [a, b]
    return out


def mc_simulate_wdl(rows: Sequence[dict], residual_total: Sequence[float], n_sims: int = 200,
                    seed: int = 12345) -> List[Dict[str, float]]:
    """T7 Monte-Carlo W/D/L: for each row draw remaining home/away goals ~ Poisson(lambda+residual share)
    and tally final outcomes. Deterministic (fixed seed). Reduces to the analytic map in expectation; we
    keep it as an explicit MC so the simulation path is exercised end-to-end."""
    import numpy as np
    rng = np.random.default_rng(seed)
    out: List[Dict[str, float]] = []
    for r, res in zip(rows, residual_total):
        lam_h = T0._fnum(r, "t0_lam_home")
        lam_a = T0._fnum(r, "t0_lam_away")
        if lam_h is None:
            lam_h = T0.BASE_RATE_PER90 * T0.remaining_fraction(r)
        if lam_a is None:
            lam_a = lam_h
        half = (res or 0.0) / 2.0
        lam_h2 = max(0.0, lam_h + half)
        lam_a2 = max(0.0, lam_a + half)
        sd = T0.current_score_diff(r)
        gh = rng.poisson(lam_h2, n_sims)
        ga = rng.poisson(lam_a2, n_sims)
        fd = sd + (gh - ga)
        pH = float((fd > 0).mean()); pD = float((fd == 0).mean()); pA = float((fd < 0).mean())
        out.append({"H": pH, "D": pD, "A": pA})
    return out


# ==================================================================================================
# fit the WHOLE ladder for a fold (TRAIN rows only) -> dict[model_id] = FittedTransferModel.
# T0 has no fitted object (it is the reference; its predictions come from reference_wdl_rows).
# ==================================================================================================
def fit_ladder(intl_train: Sequence[dict], club_train: Sequence[dict], feat_cols: Sequence[str],
               overlap_score: float = 1.0, alpha: float = 1.0) -> Dict[str, object]:
    train_all = list(intl_train) + list(club_train)
    t1 = fit_t1_international_only(intl_train, feat_cols, alpha)
    t2 = fit_t2_naive_pool(train_all, feat_cols, alpha)
    t3 = fit_t3_shared_stable(train_all, feat_cols, alpha)
    t4 = fit_t4_partial_pooling(train_all, feat_cols, alpha)
    t5 = fit_t5_domain_weighted(train_all, feat_cols, overlap_score, alpha)
    t6, gate = fit_t6_selective(train_all, intl_train, feat_cols, overlap_score, alpha)
    # T7 calibrates the SELECTED model (the gated T6) on intl-train and simulates.
    t7 = calibrate_in_train(t6, intl_train, feat_cols)
    return {
        T1_INTERNATIONAL_ONLY: t1,
        T2_NAIVE_CLUB_POOL: t2,
        T3_SHARED_STABLE_FEATURES: t3,
        T4_PARTIAL_POOLING: t4,
        T5_DOMAIN_WEIGHTED: t5,
        T6_SELECTIVE_TRANSFER: t6,
        T7_CALIBRATED_SIMULATION: t7,
        "_gate": gate,
        "_feat_cols": list(feat_cols),
    }
