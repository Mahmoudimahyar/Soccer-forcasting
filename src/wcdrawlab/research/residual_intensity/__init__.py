"""Residual goal-intensity model package (Phase 2).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Treats the remaining-time Poisson model (W2) as a REFERENCE INTENSITY -- home & away remaining-goal
rates -- NOT a competing classifier. Every model in this package is expressed RELATIVE to W2: it either
(a) reproduces the W2 reference (r0/i0/h0), or (b) estimates an event-process correction to the W2
intensities under a deterministic availability gate, blended onto W2 by a selectively-chosen weight that
ALWAYS permits alpha=0 (pure W2 fallback).

Reuses (does NOT reinvent):
  * wcdrawlab.research.dynamic_models   -- regularized fitters, graceful-unknown FeatureSpace,
                                           IsotonicCalibrator, the parameter-free remaining-time Poisson.
  * wcdrawlab.research.event_process.models -- IntensityWDL (side-specific intensity heads), the exact
                                           Poisson convolution, the e2/W2 reference, the ClubAuxRep.
  * wcdrawlab.research.event_process.eval   -- the leakage-safe joined snapshot/target loader + no-2026.

Submodules:
  features        6 interpretable feature families incl. the W2 reference intensities.
  availability    deterministic per-feature availability gate (never zero-fills an unavailable feature).
  regimes         interpretable regime classifier on causal availability/state (NOT an outcome model).
  selective_gate  fallback_to_w2 / low / full correction; training-chosen thresholds; alpha=0 permitted.
  simulation      Monte-Carlo remaining-score simulation from intensities -> H/D/A simplex.
  calibration     isotonic / logistic, in-train-only.
  datasets        load+annotate the joined panel (reuses event_process eval); LOCO folds; synthetic gen.
  quality         leakage / availability / simplex / no-2026 audits.
  registry        canonical IDs only.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

from wcdrawlab.research import dynamic_models as DM
from wcdrawlab.research.event_process import models as EPM

from . import registry  # noqa: F401
from . import features  # noqa: F401
from . import availability  # noqa: F401
from . import regimes  # noqa: F401
from . import selective_gate  # noqa: F401
from . import simulation  # noqa: F401
from . import calibration  # noqa: F401
from . import datasets  # noqa: F401
from . import quality  # noqa: F401

from .features import (W2_BASE_RATE_PER90, _remaining_fraction, _current_diff, fnum,
                       columns_for, REFERENCE_STATE_COLS, RECENT_CHANCE_COLS,
                       POSSESSION_TERRITORY_COLS, TRANSITION_COLS, SET_PIECE_COLS,
                       QUALITY_AVAILABILITY_COLS)
from .registry import REFERENCE_IDS, ARTIFACT_LABELS, assert_canonical

PACKAGE_VERSION = "residual_intensity_v1"
WDL = ["H", "D", "A"]
EPS = 1e-9

__all__ = [
    "registry", "features", "availability", "regimes", "selective_gate", "simulation",
    "calibration", "datasets", "quality",
    "w2_reference_r0", "w2_home_away_i0", "w2_implied_h0",
    "build_intensity_glm_r1", "build_selective_correction_r4", "build_calibrated_simulation_r5",
    "residual_predictors", "self_test", "PACKAGE_VERSION", "ARTIFACT_LABELS",
]


# =================================================================================================
# W2 REFERENCE (parameter-free) -- residual.r0 / intensity.i0 / horizon.h0 anchors
# =================================================================================================
def w2_intensities(row: dict) -> "tuple[float, float]":
    """W2 home/away remaining-goal intensities (the i0 reference). Both teams share the league base rate
    scaled by remaining regulation time -- identical to the locked event_process e2 reference."""
    lam = W2_BASE_RATE_PER90 * _remaining_fraction(row)
    return lam, lam


def w2_home_away_i0(row: dict) -> Dict[str, float]:
    """research.intensity.w2_home_away_i0 -- the side-specific W2 reference intensities."""
    lh, la = w2_intensities(row)
    return {"lam_home": lh, "lam_away": la}


def w2_reference_r0(row: dict) -> Dict[str, float]:
    """research.residual.w2_reference_r0 -- W2 reference WDL via exact Poisson convolution."""
    lh, la = w2_intensities(row)
    return simulation.analytic_wdl(lh, la, _current_diff(row))


def w2_implied_h0(row: dict, horizon_min: float) -> float:
    """research.horizon.w2_implied_h0 -- W2-implied P(any goal by either side in the next `horizon_min`).
    Both teams at the league base rate over the horizon fraction; P(>=1) = 1 - exp(-(lam_h+lam_a))."""
    frac = min(1.0, max(0.0, horizon_min / 90.0))
    lam = W2_BASE_RATE_PER90 * frac
    return 1.0 - math.exp(-(2.0 * lam))


# =================================================================================================
# residual.intensity_glm_r1 / intensity.event_residual_home_away_i1 -- event-process intensity GLM.
# Reuses EPM.IntensityWDL (two ridge heads predicting side-specific remaining goals) under the
# availability gate: only columns AVAILABLE on TRAIN feed the heads; the FeatureSpace handles per-row
# missingness (TRAIN-mean impute + __unknown indicator). Falls back to W2 when the heads cannot fit.
# =================================================================================================
def _gated_cols(train_rows: Sequence[dict], candidate_cols: Sequence[str],
                min_coverage: float = 0.0) -> List[str]:
    return availability.gate_columns(train_rows, candidate_cols, min_coverage=min_coverage)


def build_intensity_glm_r1(train_rows: Sequence[dict],
                           candidate_cols: Optional[Sequence[str]] = None,
                           l2: float = 1.0) -> "EPM.IntensityWDL":
    """Fit the event-process intensity GLM (ridge intensity heads + in-train isotonic WDL calibration).
    Columns are availability-gated on TRAIN so an everywhere-unavailable feature can never feed a head."""
    cand = list(candidate_cols) if candidate_cols is not None else (
        columns_for(["recent_chance", "possession_territory", "transition", "set_pieces"]))
    cols = _gated_cols(train_rows, cand) or list(REFERENCE_STATE_COLS)
    return EPM.IntensityWDL(cols, with_anchor=True, l2=l2).fit(train_rows, target_key="target_wdl")


def intensity_heads_r1(train_rows: Sequence[dict],
                       candidate_cols: Optional[Sequence[str]] = None,
                       l2: float = 1.0) -> Callable[[dict], Dict[str, float]]:
    """Return a side-specific intensity predictor (lam_home/lam_away) for intensity.i1, gated + fit on
    TRAIN. Falls back to the W2 reference when the heads are unavailable."""
    m = build_intensity_glm_r1(train_rows, candidate_cols, l2=l2)

    def _predict(row: dict) -> Dict[str, float]:
        lh, la = m._raw_intensities(row)
        return {"lam_home": lh, "lam_away": la}

    return _predict


# =================================================================================================
# residual.event_process_boost_r3 -- HistGradientBoosting intensity (small PREDECLARED grid only).
# Predicts side-specific log(1+remaining goals); converts to lam via expm1; convolves; (caller may
# calibrate). Falls back to W2 if sklearn/HGB unavailable or no usable labels.
# =================================================================================================
_HGB_GRID = {"max_depth": [3], "learning_rate": [0.1], "max_iter": [120], "min_samples_leaf": [25]}


class _HGBIntensity:
    """Two HistGradientBoosting regressors for side-specific remaining goals. Predeclared 1-point grid
    (no search / no test-tuning). Falls back to W2 when it cannot fit."""

    def __init__(self, cols: Sequence[str]):
        self.cols = list(cols)
        self.mh = None
        self.ma = None
        self.ok = False

    def _matrix(self, rows: Sequence[dict]):
        import numpy as np
        X = []
        for r in rows:
            X.append([float(fnum(r, c)) if fnum(r, c) is not None else float("nan") for c in self.cols])
        return np.asarray(X, dtype=float)

    def fit(self, train_rows: Sequence[dict]) -> "_HGBIntensity":
        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
        except Exception:
            return self
        usable = [r for r in train_rows
                  if r.get("rem_goals_home") is not None and r.get("rem_goals_away") is not None]
        if len(usable) < 30 or not self.cols:
            return self
        import numpy as np
        X = self._matrix(usable)
        yh = np.array([math.log1p(max(0.0, float(r["rem_goals_home"]))) for r in usable])
        ya = np.array([math.log1p(max(0.0, float(r["rem_goals_away"]))) for r in usable])
        kw = dict(max_depth=_HGB_GRID["max_depth"][0], learning_rate=_HGB_GRID["learning_rate"][0],
                  max_iter=_HGB_GRID["max_iter"][0], min_samples_leaf=_HGB_GRID["min_samples_leaf"][0],
                  random_state=0)
        self.mh = HistGradientBoostingRegressor(**kw).fit(X, yh)
        self.ma = HistGradientBoostingRegressor(**kw).fit(X, ya)
        self.ok = True
        return self

    def intensities(self, row: dict) -> "tuple[float, float]":
        if not self.ok:
            return w2_intensities(row)
        import numpy as np
        x = np.asarray([[float(fnum(row, c)) if fnum(row, c) is not None else float("nan")
                         for c in self.cols]], dtype=float)
        lh = max(0.0, math.expm1(float(self.mh.predict(x)[0])))
        la = max(0.0, math.expm1(float(self.ma.predict(x)[0])))
        return lh, la

    def predict_one(self, row: dict) -> Dict[str, float]:
        lh, la = self.intensities(row)
        return simulation.analytic_wdl(lh, la, _current_diff(row))


def build_event_process_boost_r3(train_rows: Sequence[dict],
                                 candidate_cols: Optional[Sequence[str]] = None) -> "_HGBIntensity":
    cand = list(candidate_cols) if candidate_cols is not None else (
        columns_for(["recent_chance", "possession_territory", "transition", "set_pieces",
                     "quality_availability"]))
    cols = _gated_cols(train_rows, cand)
    return _HGBIntensity(cols).fit(train_rows)


# =================================================================================================
# residual.selective_correction_r4 -- selective correction of W2 (alpha=0 fallback permitted).
# Reference = w2_reference_r0; correction = the intensity GLM r1. The gate chooses, IN-TRAIN, the
# completeness thresholds + alpha bands that beat W2 (or degenerates to alpha=0 everywhere).
# =================================================================================================
class SelectiveCorrection:
    """research.residual.selective_correction_r4. Holds the W2 reference, a fitted correction model, and
    a fitted SelectiveGate. predict_one blends per the gate's per-row alpha (0 => pure W2)."""

    def __init__(self, candidate_cols: Optional[Sequence[str]] = None, l2: float = 1.0):
        self.candidate_cols = (list(candidate_cols) if candidate_cols is not None else
                               columns_for(["recent_chance", "possession_territory", "transition",
                                            "set_pieces"]))
        self.l2 = l2
        self.correction: Optional[EPM.IntensityWDL] = None
        self.gate: Optional[selective_gate.SelectiveGate] = None

    def fit(self, train_rows: Sequence[dict]) -> "SelectiveCorrection":
        # correction is fit on FULL train for predict-time use ...
        self.correction = build_intensity_glm_r1(train_rows, self.candidate_cols, l2=self.l2)
        # ... but alpha is selected HONESTLY on internal held-out folds (the correction is refit inside
        # each internal fold). This makes the gate see the true generalization gap, so it degenerates to
        # alpha=0 (pure W2 fallback) when the event-process correction does not generalize. This is the
        # honest reading of "alpha chosen in-train": chosen using only TRAIN, but never scored on the same
        # rows the correction memorized.
        cols = self.candidate_cols
        l2 = self.l2

        def _corr_factory(internal_train):
            return build_intensity_glm_r1(internal_train, cols, l2=l2).predict_one

        gate = selective_gate.SelectiveGate(candidate_cols=self.candidate_cols)
        gate.fit_cv(train_rows, p_w2=w2_reference_r0, correction_factory=_corr_factory,
                    fold_key="competition", target_key="target_wdl")
        self.gate = gate
        return self

    def predict_one(self, row: dict) -> Dict[str, float]:
        if self.gate is None or self.correction is None:
            return w2_reference_r0(row)
        return self.gate.predict_one(row, p_w2=w2_reference_r0, p_corr=self.correction.predict_one)

    def diagnostics(self) -> Dict[str, object]:
        return dict(self.gate.fit_diagnostics) if self.gate is not None else {}


def build_selective_correction_r4(train_rows: Sequence[dict],
                                  candidate_cols: Optional[Sequence[str]] = None,
                                  l2: float = 1.0) -> "SelectiveCorrection":
    return SelectiveCorrection(candidate_cols, l2=l2).fit(train_rows)


# =================================================================================================
# residual.calibrated_simulation_r5 -- Monte-Carlo simulation from event-process intensities + in-train
# WDL calibration. Uses the r1 intensity heads to get (lam_h, lam_a), simulates remaining score, then
# fits a per-class WDLCalibrator on TRAIN pooled-vs-outcome (in-train only).
# =================================================================================================
class CalibratedSimulation:
    """research.residual.calibrated_simulation_r5."""

    def __init__(self, candidate_cols: Optional[Sequence[str]] = None, l2: float = 1.0,
                 n_sims: int = 4000, method: str = "isotonic", seed: int = 12345):
        self.candidate_cols = candidate_cols
        self.l2 = l2
        self.n_sims = n_sims
        self.method = method
        self.seed = seed
        self.heads: Optional[EPM.IntensityWDL] = None
        self.cal: Optional[calibration.WDLCalibrator] = None

    def _raw(self, row: dict) -> Dict[str, float]:
        lh, la = (self.heads._raw_intensities(row) if self.heads is not None else w2_intensities(row))
        return simulation.simulate_wdl(lh, la, _current_diff(row), n_sims=self.n_sims, seed=self.seed)

    def fit(self, train_rows: Sequence[dict]) -> "CalibratedSimulation":
        self.heads = build_intensity_glm_r1(train_rows, self.candidate_cols, l2=self.l2)
        cal_rows = [r for r in train_rows if r.get("target_wdl") in WDL]
        if cal_rows:
            raws = [self._raw(r) for r in cal_rows]
            ys = [r["target_wdl"] for r in cal_rows]
            self.cal = calibration.WDLCalibrator(self.method).fit(raws, ys)
        return self

    def predict_one(self, row: dict) -> Dict[str, float]:
        raw = self._raw(row)
        return self.cal.transform_one(raw) if (self.cal is not None and self.cal.fitted) else raw


def build_calibrated_simulation_r5(train_rows: Sequence[dict],
                                   candidate_cols: Optional[Sequence[str]] = None,
                                   l2: float = 1.0, n_sims: int = 4000) -> "CalibratedSimulation":
    return CalibratedSimulation(candidate_cols, l2=l2, n_sims=n_sims).fit(train_rows)


# =================================================================================================
# residual.club_auxiliary_transfer_r6 -- frozen CLUB-trained representation transferred onto intl rows.
# Reuses EPM.ClubAuxRep (trained on club rows ONLY); annotates intl rows with the frozen scalar, which
# the intensity GLM then consumes as one extra availability-gated feature. Club rows never become intl
# test rows.
# =================================================================================================
def build_club_auxiliary_transfer_r6(train_rows: Sequence[dict],
                                     club_rows: Sequence[dict],
                                     candidate_cols: Optional[Sequence[str]] = None,
                                     l2: float = 1.0):
    rep = EPM.ClubAuxRep().fit(club_rows)
    rep.annotate(train_rows)  # attach 'aux_club_intensity_diff' to TRAIN intl rows
    cand = list(candidate_cols) if candidate_cols is not None else (
        columns_for(["recent_chance", "possession_territory", "transition", "set_pieces"]))
    if rep.trained_on_club_rows > 0:
        cand = cand + ["aux_club_intensity_diff"]
    model = build_intensity_glm_r1(train_rows, cand, l2=l2)
    return model, rep


# =================================================================================================
# canonical predictor factory (TRAIN -> {model_id: predict_one}). Mirrors event_process's factory shape
# so the shared eval harness can score these families with no changes.
# =================================================================================================
def residual_predictors(train_rows: Sequence[dict],
                        club_rows: Optional[Sequence[dict]] = None) -> Dict[str, Callable[[dict], Dict[str, float]]]:
    """Build the residual WDL family {r0, r1, r3, r4, r5(, r6)} as TRAIN-fit predict_one callables.
    r0 is the parameter-free W2 reference; the rest are event-process corrections expressed relative to
    it. r6 is included only when club auxiliary rows are supplied."""
    preds: Dict[str, Callable[[dict], Dict[str, float]]] = {}
    preds[assert_canonical("research.residual.w2_reference_r0")] = w2_reference_r0
    preds[assert_canonical("research.residual.intensity_glm_r1")] = \
        build_intensity_glm_r1(train_rows).predict_one
    preds[assert_canonical("research.residual.event_process_boost_r3")] = \
        build_event_process_boost_r3(train_rows).predict_one
    preds[assert_canonical("research.residual.selective_correction_r4")] = \
        build_selective_correction_r4(train_rows).predict_one
    preds[assert_canonical("research.residual.calibrated_simulation_r5")] = \
        build_calibrated_simulation_r5(train_rows).predict_one
    if club_rows:
        model, _rep = build_club_auxiliary_transfer_r6(train_rows, club_rows)
        preds[assert_canonical("research.residual.club_auxiliary_transfer_r6")] = model.predict_one
    return preds


# =================================================================================================
# SELF-TEST (deterministic). status=complete only if these pass on REAL snapshot rows.
# =================================================================================================
def _logloss(p: Dict[str, float], y: str) -> float:
    return -math.log(max(1e-12, float(p.get(y, 0.0))))


def self_test(rows: Optional[Sequence[dict]] = None) -> Dict[str, object]:
    """Run the three mandated self-tests + a small eval. If `rows` is None, attempts to load the REAL
    joined snapshot panel; falls back to the deterministic synthetic panel ONLY for the structural
    checks (the spec's status=complete is gated on the REAL-row path succeeding).

    Checks:
      1. availability gate EXCLUDES a feature that is missing (no-xG row -> xG col unavailable;
         everywhere-unavailable col dropped by gate_columns).
      2. selective gate returns alpha=0 fallback on low completeness (and is reachable in general).
      3. simulation of two intensities yields a valid H/D/A simplex (analytic + Monte-Carlo).
    """
    out: Dict[str, object] = {"labels": ARTIFACT_LABELS}

    # ---- obtain rows: prefer REAL -----------------------------------------------------------------
    real_used = False
    if rows is None:
        try:
            bundle = datasets.load_residual_rows()
            rows = list(bundle["rows"])
            real_used = True
            out["data_source"] = "real_snapshot_panel"
            out["n_rows"] = len(rows)
            out["n_matches"] = bundle["n_matches"]
            out["n_competitions"] = bundle["n_competitions"]
        except datasets.DataInsufficient as e:
            out["data_source"] = "synthetic_fallback"
            out["data_insufficient_reason"] = str(e)
            rows = datasets.synthetic_rows()
    else:
        rows = list(rows)
        out["data_source"] = "provided_rows"

    rows = list(rows)

    # ---- (1) availability gate excludes a missing feature -----------------------------------------
    # Find a row whose xg_present is False (real panel has 370 such rows); its xG columns must be
    # unavailable, and gate_columns over xG-less rows must DROP an everywhere-unavailable xG column.
    no_xg_rows = [r for r in rows if str(r.get("xg_present")).strip().lower() == "false"]
    a1 = {}
    if no_xg_rows:
        r0 = no_xg_rows[0]
        xg_avail = availability.is_available(r0, "cum_xg_home")
        gated = availability.gate_columns(no_xg_rows, ["cum_xg_home", "cum_xg_diff", "goals_diff"])
        a1 = {
            "tested_on": "no_xg_row",
            "cum_xg_home_available_on_no_xg_row": xg_avail,            # must be False
            "gated_excludes_xg": "cum_xg_home" not in gated and "cum_xg_diff" not in gated,
            "gated_keeps_available_state": "goals_diff" in gated,
            "passed": (xg_avail is False) and ("cum_xg_home" not in gated) and ("goals_diff" in gated),
        }
    else:
        # synthetic panel always contains no-xG rows; if somehow none, force one
        forced = dict(rows[0]); forced["xg_present"] = "False"; forced.pop("cum_xg_home", None)
        xg_avail = availability.is_available(forced, "cum_xg_home")
        gated = availability.gate_columns([forced], ["cum_xg_home", "goals_diff"])
        a1 = {"tested_on": "forced_no_xg_row",
              "cum_xg_home_available_on_no_xg_row": xg_avail,
              "gated_excludes_xg": "cum_xg_home" not in gated,
              "passed": (xg_avail is False) and ("cum_xg_home" not in gated)}
    out["test_availability_gate_excludes_missing"] = a1

    # ---- (2) selective gate returns alpha=0 fallback on low completeness --------------------------
    # Fit the gate on a TRAIN slice; assert (a) a low-completeness row -> decision fallback_to_w2 /
    # alpha 0, and (b) alpha=0 is reachable by construction (a synthetic empty-evidence row).
    train = rows
    sc = build_selective_correction_r4(train)
    gate = sc.gate
    # construct a deliberately low-completeness row (strip event-process cells; keep only score/clock)
    low_row = {"snapshot_minute": 30.0, "remaining_regulation_min": 60.0,
               "goals_home": 0, "goals_away": 0, "goals_diff": 0, "period": 1,
               "players_diff": 0, "xg_present": "False"}
    availability.annotate_completeness([low_row], features.ALL_FEATURE_COLS)
    low_completeness = low_row["ri_completeness"]
    low_decision = gate.decision(low_row)
    low_alpha = gate.alpha_for(low_row)
    blended = sc.predict_one(low_row)  # must equal pure W2 when alpha==0
    w2_p = w2_reference_r0(low_row)
    equal_to_w2 = all(abs(blended[k] - w2_p[k]) < 1e-9 for k in WDL)
    a2 = {
        "low_completeness": round(float(low_completeness), 4),
        "decision_on_low_completeness": low_decision,
        "alpha_on_low_completeness": low_alpha,
        "alpha0_reachable": True,  # by construction: completeness 0 -> fallback band -> alpha 0
        "blend_equals_pure_w2_when_alpha0": equal_to_w2,
        "gate_diagnostics": sc.diagnostics(),
        "passed": (low_decision == "fallback_to_w2") and (low_alpha == 0.0) and equal_to_w2,
    }
    out["test_selective_gate_alpha0_fallback"] = a2

    # ---- (3) simulation of two intensities -> valid H/D/A simplex --------------------------------
    sims = []
    cases = [(1.2, 0.8, 0), (0.3, 2.1, -1), (0.0, 0.0, 2), (2.5, 2.5, 0)]
    all_ok = True
    for (lh, la, d) in cases:
        pa = simulation.analytic_wdl(lh, la, d)
        pm = simulation.simulate_wdl(lh, la, d, n_sims=3000, seed=99)
        ok = simulation.is_simplex(pa) and simulation.is_simplex(pm)
        all_ok = all_ok and ok
        sims.append({"lam_h": lh, "lam_a": la, "diff": d,
                     "analytic": {k: round(pa[k], 4) for k in WDL},
                     "mc": {k: round(pm[k], 4) for k in WDL}, "simplex_ok": ok})
    out["test_simulation_simplex"] = {"cases": sims, "passed": all_ok}

    # ---- small leakage + simplex sanity on the model outputs over a sample ------------------------
    feat_cols = columns_for(["reference_state", "recent_chance", "possession_territory",
                             "transition", "set_pieces", "quality_availability"])
    lk = quality.leakage_audit(rows[: min(500, len(rows))], feat_cols)
    out["leakage_audit"] = {"ok": lk["ok"], "no_target_in_features": lk["no_target_in_features"],
                            "forbidden_present": lk["forbidden_feature_cols_present"]}

    # predict_one over a few rows must be a valid simplex for every residual model
    preds = residual_predictors(train)
    sample = rows[: min(40, len(rows))]
    model_simplex_ok = True
    per_model_ll: Dict[str, float] = {}
    for mid, fn in preds.items():
        lls = []
        for r in sample:
            p = fn(r)
            if not quality.simplex_audit(p):
                model_simplex_ok = False
            if r.get("target_wdl") in WDL:
                lls.append(_logloss(p, r["target_wdl"]))
        per_model_ll[mid] = round(sum(lls) / len(lls), 6) if lls else None
    out["model_output_simplex_ok"] = model_simplex_ok
    out["sample_train_logloss"] = per_model_ll

    passed = (a1.get("passed") and a2.get("passed") and out["test_simulation_simplex"]["passed"]
              and lk["ok"] and model_simplex_ok)
    out["all_passed"] = bool(passed)
    out["real_rows_used"] = real_used
    # status=complete requires the REAL-row path AND all self-tests passing.
    out["status"] = "complete" if (passed and real_used) else ("partial" if passed else "failed")
    return out
