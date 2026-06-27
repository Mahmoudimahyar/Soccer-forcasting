"""Residual goal-intensity MODEL families (Phase 3).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module is the single, canonical home for the three model families enumerated in the build spec.
Every model is expressed RELATIVE to the remaining-time Poisson reference (W2): it either reproduces W2
(``*_r0`` / ``*_i0`` / ``*_h0``) or estimates an event-process correction to the W2 home/away
intensities under the deterministic availability gate, ALWAYS permitting a pure-W2 fallback.

  intensity.*  -- side-specific (home & away) remaining-goal INTENSITY:
                    i0  w2_home_away_i0               W2 reference intensities (parameter-free)
                    i1  event_residual_home_away_i1   event-process residual correction of W2 per side
                    i2  regime_specific_i2            regime-conditioned residual (interpretable regimes)
                    i3  club_transfer_i3              + frozen club-transfer scalar feature

  horizon.*    -- near-term scoring window (5/10/15 min, RIGHT-CENSORED) as a competing-risk hazard:
                    h0  w2_implied_h0                 W2-implied P(any goal in window)
                    h1  xg_residual_h1                + cumulative/rolling xG residual
                    h2  possession_transition_h2      + possession / territory / transition state
                    h3  full_event_process_h3         + full event-process state
                    h4  selective_gate_h4             selective gate over {h0..h3} (training-chosen)

  residual.*   -- W/D/L: estimate remaining home/away intensity, correct W2 ONLY via residual, simulate
                  remaining score, add the current score, calibrate in-train:
                    r0  w2_reference_r0               W2 reference WDL (parameter-free)
                    r1  intensity_glm_r1              regularized event-process intensity GLM
                    r2  competing_risk_r2             regularized discrete-time competing-risk hazard
                    r3  event_process_boost_r3        HistGradientBoosting intensity (predeclared grid)
                    r4  selective_correction_r4       selective correction of W2 (alpha in-train; 0 ok)
                    r5  calibrated_simulation_r5       Monte-Carlo simulation + in-train calibration
                    r6  club_auxiliary_transfer_r6     frozen club-trained representation transferred in

REUSE (does NOT reinvent): the heavy lifting already lives in the package __init__ (the W2 anchors r0/i0/
h0, the intensity GLM r1, the HGB boost r3, the selective correction r4, the calibrated simulation r5,
the club transfer r6) and in the locked event_process / dynamic_models modules (ridge intensity heads,
graceful-unknown FeatureSpace, isotonic calibrator, exact Poisson convolution). This module imports those
verbatim and ADDS the remaining declared families: the competing-risk hazard (r2), the regime-specific
intensity (i2), the club-transfer intensity (i3), and the near-term competing-risk horizon heads
(h1..h4). It then exposes the three canonical predictor factories the eval harness consumes.

LEAKAGE: every head is fit on TRAIN rows only; the side-specific remaining-goal labels
(rem_goals_home/away) and the horizon labels (any_goal_next{5,10,15}m) are used ONLY to fit on TRAIN and
NEVER enter a feature space; the availability gate drops everywhere-unavailable columns; xG columns are
unavailable on rows whose source carries no xG. Club rows train aux reps but are NEVER test rows.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

from wcdrawlab.research import dynamic_models as DM
from wcdrawlab.research.event_process import models as EPM

from . import availability as AV
from . import calibration as CAL
from . import features as F
from . import regimes as RG
from . import registry as REG
from . import selective_gate as SG
from . import simulation as SIM
from .registry import assert_canonical

# The package __init__ already builds the W2 anchors + r1/r3/r4/r5/r6. Import them so models.py is the
# single canonical surface without duplicating their (already self-tested) implementations.
from . import (  # noqa: E402
    w2_intensities, w2_home_away_i0, w2_reference_r0, w2_implied_h0,
    build_intensity_glm_r1, intensity_heads_r1,
    build_event_process_boost_r3, build_selective_correction_r4,
    build_calibrated_simulation_r5, build_club_auxiliary_transfer_r6,
)

MODELS_VERSION = "residual_intensity_models_v1"
WDL = ["H", "D", "A"]
HORIZONS = (5, 10, 15)
EPS = 1e-12
ARTIFACT_LABELS = REG.ARTIFACT_LABELS

# default candidate column-sets (availability-gated on TRAIN before any head sees them)
_CORRECTION_FAMILIES = ["recent_chance", "possession_territory", "transition", "set_pieces"]
_FULL_FAMILIES = ["recent_chance", "possession_territory", "transition", "set_pieces",
                  "quality_availability"]


def _gated(train_rows, families, extra=None):
    cand = F.columns_for(families) + list(extra or [])
    return AV.gate_columns(train_rows, cand) or list(F.REFERENCE_STATE_COLS)


# =================================================================================================
# INTENSITY family  (side-specific home/away remaining-goal rates)
# =================================================================================================
# i0 = w2_home_away_i0 (imported); i1 = event_residual_home_away_i1 via the r1 heads (imported).

def build_event_residual_home_away_i1(train_rows: Sequence[dict],
                                      candidate_cols: Optional[Sequence[str]] = None,
                                      l2: float = 1.0) -> Callable[[dict], Dict[str, float]]:
    """research.intensity.event_residual_home_away_i1 -- side-specific intensities from the event-process
    GLM heads, expressed as a residual ON TOP of the W2 reference: lam = lam_w2 * exp(delta) where the
    heads predict the (log) correction. Falls back to the W2 reference per side when a head is
    unavailable. Returns {lam_home, lam_away}. (Thin wrapper over the locked r1 heads so i1 and r1 share
    one fitted object.)"""
    return intensity_heads_r1(train_rows, candidate_cols, l2=l2)


class RegimeSpecificIntensity:
    """research.intensity.regime_specific_i2 -- regime-conditioned event-process intensities.

    The interpretable regime label (game-state x evidence-tier, a deterministic function of CAUSAL state
    + availability only -- never a target) partitions TRAIN. A separate event-process intensity GLM is
    fit per regime that has enough labelled rows; sparse regimes fall back to a single pooled GLM, and
    that in turn falls back to the W2 reference. Predict routes a row to its regime's head. This lets the
    correction differ between e.g. 'level_late|rich' and 'two_plus_lead|sparse' WITHOUT any test-tuning:
    the routing key is causal and frozen, and each head is an ordinary in-train GLM."""

    def __init__(self, candidate_cols: Optional[Sequence[str]] = None, l2: float = 1.0,
                 min_regime_rows: int = 120):
        self.candidate_cols = candidate_cols
        self.l2 = l2
        self.min_regime_rows = min_regime_rows
        self.pooled: Optional[EPM.IntensityWDL] = None
        self.by_regime: Dict[str, EPM.IntensityWDL] = {}
        self.regime_rows: Dict[str, int] = {}

    def fit(self, train_rows: Sequence[dict]) -> "RegimeSpecificIntensity":
        rows = list(train_rows)
        RG.annotate(rows, F.ALL_FEATURE_COLS)
        self.pooled = build_intensity_glm_r1(rows, self.candidate_cols, l2=self.l2)
        groups: Dict[str, List[dict]] = {}
        for r in rows:
            groups.setdefault(r.get("ri_regime", "unknown"), []).append(r)
        for reg, grp in groups.items():
            labelled = [r for r in grp if r.get("rem_goals_home") is not None]
            self.regime_rows[reg] = len(labelled)
            if len(labelled) >= self.min_regime_rows:
                self.by_regime[reg] = build_intensity_glm_r1(grp, self.candidate_cols, l2=self.l2)
        return self

    def _head_for(self, row: dict) -> "EPM.IntensityWDL":
        reg = row.get("ri_regime") or RG.classify(row, F.ALL_FEATURE_COLS)
        return self.by_regime.get(reg, self.pooled)

    def intensities(self, row: dict) -> Dict[str, float]:
        head = self._head_for(row)
        if head is None:
            lh, la = w2_intensities(row)
        else:
            lh, la = head._raw_intensities(row)
        return {"lam_home": lh, "lam_away": la}

    def predict_one(self, row: dict) -> Dict[str, float]:
        head = self._head_for(row)
        return head.predict_one(row) if head is not None else w2_reference_r0(row)

    def diagnostics(self) -> Dict[str, object]:
        return {"n_regime_heads": len(self.by_regime), "min_regime_rows": self.min_regime_rows,
                "rows_per_regime": dict(sorted(self.regime_rows.items()))}


def build_regime_specific_i2(train_rows: Sequence[dict],
                             candidate_cols: Optional[Sequence[str]] = None,
                             l2: float = 1.0) -> RegimeSpecificIntensity:
    return RegimeSpecificIntensity(candidate_cols, l2=l2).fit(train_rows)


class ClubTransferIntensity:
    """research.intensity.club_transfer_i3 -- event-process intensities with the frozen club-trained
    scalar (aux_club_intensity_diff) added as ONE extra availability-gated feature. The club aux rep is
    trained on CLUB rows only (never intl test rows); intl TRAIN rows are annotated with the frozen
    scalar, then the intensity GLM consumes it. When no club rows are supplied, degrades exactly to i1."""

    def __init__(self, candidate_cols: Optional[Sequence[str]] = None, l2: float = 1.0):
        self.candidate_cols = candidate_cols
        self.l2 = l2
        self.model: Optional[EPM.IntensityWDL] = None
        self.rep: Optional[EPM.ClubAuxRep] = None
        self.used_club_rows = 0

    def fit(self, train_rows: Sequence[dict], club_rows: Optional[Sequence[dict]] = None
            ) -> "ClubTransferIntensity":
        if club_rows:
            self.model, self.rep = build_club_auxiliary_transfer_r6(
                train_rows, club_rows, self.candidate_cols, l2=self.l2)
            self.used_club_rows = self.rep.trained_on_club_rows
        else:
            self.model = build_intensity_glm_r1(train_rows, self.candidate_cols, l2=self.l2)
        return self

    def _annotate(self, row: dict) -> None:
        if self.rep is not None and "aux_club_intensity_diff" not in row:
            row["aux_club_intensity_diff"] = self.rep.value(row)

    def intensities(self, row: dict) -> Dict[str, float]:
        self._annotate(row)
        lh, la = (self.model._raw_intensities(row) if self.model is not None else w2_intensities(row))
        return {"lam_home": lh, "lam_away": la}

    def predict_one(self, row: dict) -> Dict[str, float]:
        self._annotate(row)
        return self.model.predict_one(row) if self.model is not None else w2_reference_r0(row)


def build_club_transfer_i3(train_rows: Sequence[dict], club_rows: Optional[Sequence[dict]] = None,
                           candidate_cols: Optional[Sequence[str]] = None,
                           l2: float = 1.0) -> ClubTransferIntensity:
    return ClubTransferIntensity(candidate_cols, l2=l2).fit(train_rows, club_rows)


def intensity_predictors(train_rows: Sequence[dict],
                         club_rows: Optional[Sequence[dict]] = None
                         ) -> Dict[str, Callable[[dict], Dict[str, float]]]:
    """Build the side-specific INTENSITY family {i0, i1, i2(, i3)} as TRAIN-fit {lam_home, lam_away}
    callables. i0 is the parameter-free W2 reference; i1/i2/i3 are event-process residual corrections of
    it. i3 is included only when club auxiliary rows are supplied."""
    preds: Dict[str, Callable[[dict], Dict[str, float]]] = {}
    preds[assert_canonical("research.intensity.w2_home_away_i0")] = w2_home_away_i0
    preds[assert_canonical("research.intensity.event_residual_home_away_i1")] = \
        build_event_residual_home_away_i1(train_rows)
    preds[assert_canonical("research.intensity.regime_specific_i2")] = \
        build_regime_specific_i2(train_rows).intensities
    if club_rows:
        preds[assert_canonical("research.intensity.club_transfer_i3")] = \
            build_club_transfer_i3(train_rows, club_rows).intensities
    return preds


# =================================================================================================
# RESIDUAL W/D/L family  (r2 competing-risk hazard added here; r0/r1/r3/r4/r5/r6 imported)
# =================================================================================================
class CompetingRiskWDL:
    """research.residual.competing_risk_r2 -- regularized DISCRETE-TIME competing-risk hazard over the
    remaining regulation window, converted to a final W/D/L distribution.

    Mechanism (all on TRAIN only): over the remaining minutes we model the per-side next-goal hazard as
    two regularized logistic discrete-time hazards (home-scores-next-window / away-scores-next-window),
    fit on the leakage-safe near-term labels (any side scores within 10'). The per-window hazards are
    summed over the remaining-time budget into expected remaining goals per side (a hazard->intensity
    bridge), which are then convolved with the current diff via the exact Poisson convolution and
    calibrated in-train. This is a *competing-risk* read of the same remaining-score problem: the two
    sides compete to score next; the hazards are regularized and availability-gated. Falls back to W2
    when the hazards cannot fit (no usable near-term labels)."""

    def __init__(self, candidate_cols: Optional[Sequence[str]] = None, l2: float = 1.0,
                 horizon_min: float = 10.0):
        self.candidate_cols = candidate_cols
        self.l2 = l2
        self.horizon_min = float(horizon_min)
        self.hz_home: Optional[DM.RidgeLogitBin] = None
        self.hz_away: Optional[DM.RidgeLogitBin] = None
        self.cal: Optional[CAL.WDLCalibrator] = None
        self.cols: List[str] = []

    def _space(self) -> "DM.FeatureSpace":
        return DM.FeatureSpace(self.cols, with_r2_anchor=True)

    def fit(self, train_rows: Sequence[dict]) -> "CompetingRiskWDL":
        cand = (list(self.candidate_cols) if self.candidate_cols is not None
                else F.columns_for(_CORRECTION_FAMILIES))
        self.cols = AV.gate_columns(train_rows, cand) or list(F.REFERENCE_STATE_COLS)
        h_key, a_key = "home_scores_next10m", "away_scores_next10m"
        usable_h = [r for r in train_rows if r.get(h_key) is not None and str(r.get(h_key)) != ""]
        usable_a = [r for r in train_rows if r.get(a_key) is not None and str(r.get(a_key)) != ""]
        if usable_h and len({int(float(r[h_key])) for r in usable_h}) >= 2:
            self.hz_home = DM.RidgeLogitBin(self._space()).fit(usable_h, h_key)
        if usable_a and len({int(float(r[a_key])) for r in usable_a}) >= 2:
            self.hz_away = DM.RidgeLogitBin(self._space()).fit(usable_a, a_key)
        cal_rows = [r for r in train_rows if r.get("target_wdl") in WDL]
        if cal_rows:
            raws = [self._raw_wdl(r) for r in cal_rows]
            ys = [r["target_wdl"] for r in cal_rows]
            self.cal = CAL.WDLCalibrator("isotonic").fit(raws, ys)
        return self

    def _intensities(self, row: dict) -> "tuple[float, float]":
        """Bridge the per-window competing-risk hazards to expected remaining goals per side.

        h = P(side scores in the next ``horizon_min``); per-window hazard rate ~= -ln(1-h)/horizon
        (discrete-time hazard -> continuous rate). Integrate over the remaining regulation minutes to get
        expected remaining goals lam = rate * remaining_min. Falls back per side to the W2 rate when the
        side's hazard head is unavailable so the model degrades to W2, never to nonsense."""
        rem_min = max(0.0, 90.0 * F._remaining_fraction(row))
        lam_w2 = F.W2_BASE_RATE_PER90 * F._remaining_fraction(row)

        def _side(hz):
            if hz is None:
                return lam_w2
            h = min(0.999, max(1e-6, float(hz.predict_one(row))))
            rate_per_min = -math.log(1.0 - h) / self.horizon_min
            return max(0.0, rate_per_min * rem_min)

        return _side(self.hz_home), _side(self.hz_away)

    def _raw_wdl(self, row: dict) -> Dict[str, float]:
        lh, la = self._intensities(row)
        return SIM.analytic_wdl(lh, la, F._current_diff(row))

    def predict_one(self, row: dict) -> Dict[str, float]:
        raw = self._raw_wdl(row)
        return self.cal.transform_one(raw) if (self.cal is not None and self.cal.fitted) else raw

    @property
    def have_heads(self) -> bool:
        return self.hz_home is not None or self.hz_away is not None


def build_competing_risk_r2(train_rows: Sequence[dict],
                            candidate_cols: Optional[Sequence[str]] = None,
                            l2: float = 1.0) -> CompetingRiskWDL:
    return CompetingRiskWDL(candidate_cols, l2=l2).fit(train_rows)


def residual_predictors(train_rows: Sequence[dict],
                        club_rows: Optional[Sequence[dict]] = None,
                        include_club_transfer: bool = True
                        ) -> Dict[str, Callable[[dict], Dict[str, float]]]:
    """Build the residual W/D/L family {r0, r1, r2, r3, r4, r5(, r6)} as TRAIN-fit predict_one callables.
    r0 is the parameter-free W2 reference; the rest are event-process corrections expressed relative to
    it (each ALWAYS able to fall back to r0). r6 is included only when club rows are supplied and
    ``include_club_transfer`` is True -- this is the with/without-club-transfer ablation switch."""
    preds: Dict[str, Callable[[dict], Dict[str, float]]] = {}
    preds[assert_canonical("research.residual.w2_reference_r0")] = w2_reference_r0
    preds[assert_canonical("research.residual.intensity_glm_r1")] = \
        build_intensity_glm_r1(train_rows).predict_one
    preds[assert_canonical("research.residual.competing_risk_r2")] = \
        build_competing_risk_r2(train_rows).predict_one
    preds[assert_canonical("research.residual.event_process_boost_r3")] = \
        build_event_process_boost_r3(train_rows).predict_one
    preds[assert_canonical("research.residual.selective_correction_r4")] = \
        build_selective_correction_r4(train_rows).predict_one
    preds[assert_canonical("research.residual.calibrated_simulation_r5")] = \
        build_calibrated_simulation_r5(train_rows).predict_one
    if club_rows and include_club_transfer:
        model, _rep = build_club_auxiliary_transfer_r6(train_rows, club_rows)
        preds[assert_canonical("research.residual.club_auxiliary_transfer_r6")] = model.predict_one
    return preds


# =================================================================================================
# NEAR-TERM HORIZON family  (competing-risk for 5/10/15 min separately, RIGHT-CENSORED)
# =================================================================================================
# Each horizon h in {5,10,15} predicts P(any goal by either side within h minutes). h0 is W2-implied;
# h1..h3 add event-process state as a regularized logistic hazard; h4 selectively gates h0..h3.
# Right-censoring: the label any_goal_next{h}m already counts a goal only if it occurs strictly after t
# and within min(90, t+h) (regulation), so windows truncated by full-time are correctly censored. We
# additionally DROP rows whose remaining regulation time is shorter than the horizon when FITTING a
# horizon head (a window that cannot be fully observed must not train that horizon), and at predict time
# scale the W2-implied baseline by the OBSERVABLE fraction of the window.

_HORIZON_FAMILIES = {
    "h1": ["recent_chance"],                                   # xG residual
    "h2": ["possession_territory", "transition"],              # possession / territory / transition
    "h3": _FULL_FAMILIES,                                      # full event-process state
}


def _target_key(horizon_min: int) -> str:
    return f"any_goal_next{int(horizon_min)}m"


def _observable_fraction(row: dict, horizon_min: float) -> float:
    """Fraction of the ``horizon_min`` window that lies inside regulation from the decision minute."""
    rem_min = max(0.0, 90.0 * F._remaining_fraction(row))
    if horizon_min <= 0:
        return 0.0
    return max(0.0, min(1.0, rem_min / float(horizon_min)))


def horizon_w2_implied_h0(horizon_min: int) -> Callable[[dict], float]:
    """research.horizon.w2_implied_h0 -- W2-implied P(any goal within ``horizon_min``), right-censored:
    both teams at the league base rate over the OBSERVABLE window fraction; P(>=1)=1-exp(-(lam_h+lam_a))."""
    def _predict(row: dict) -> float:
        frac = _observable_fraction(row, horizon_min) * (horizon_min / 90.0)
        lam = F.W2_BASE_RATE_PER90 * frac
        return 1.0 - math.exp(-(2.0 * lam))
    return _predict


class HorizonHazard:
    """A single horizon's event-process competing-risk hazard head: regularized logistic P(any goal in
    the next ``horizon_min``) from availability-gated event-process state, blended onto the W2-implied
    baseline and calibrated in-train. Right-censored: fit only on rows whose window is fully observable;
    predict scales toward the W2-implied baseline as the observable fraction shrinks. Falls back to the
    W2-implied baseline when the head cannot fit."""

    def __init__(self, horizon_min: int, families: Sequence[str],
                 candidate_cols: Optional[Sequence[str]] = None):
        self.horizon_min = int(horizon_min)
        self.families = list(families)
        self.candidate_cols = candidate_cols
        self.head: Optional[DM.RidgeLogitBin] = None
        self.cal: Optional[CAL.BinaryCalibrator] = None
        self.cols: List[str] = []
        self.w2 = horizon_w2_implied_h0(horizon_min)

    def fit(self, train_rows: Sequence[dict]) -> "HorizonHazard":
        cand = (list(self.candidate_cols) if self.candidate_cols is not None
                else F.columns_for(self.families))
        self.cols = AV.gate_columns(train_rows, cand) or list(F.REFERENCE_STATE_COLS)
        key = _target_key(self.horizon_min)
        # right-censoring: only rows whose full window is observable train this horizon
        fit_rows = [r for r in train_rows
                    if r.get(key) is not None and str(r.get(key)) != ""
                    and _observable_fraction(r, self.horizon_min) >= 0.999]
        if fit_rows and len({int(float(r[key])) for r in fit_rows}) >= 2:
            space = DM.FeatureSpace(self.cols, with_r2_anchor=True)
            self.head = DM.RidgeLogitBin(space).fit(fit_rows, key)
            cal_rows = [r for r in fit_rows]
            raws = [self._raw(r) for r in cal_rows]
            ys = [int(float(r[key])) for r in cal_rows]
            self.cal = CAL.BinaryCalibrator("isotonic").fit(raws, ys)
        return self

    def _raw(self, row: dict) -> float:
        if self.head is None:
            return float(self.w2(row))
        p = float(self.head.predict_one(row))
        # blend toward the W2-implied baseline by the observable fraction (a window only partly inside
        # regulation cannot be fully trusted to the head; the unobservable part defers to W2).
        frac = _observable_fraction(row, self.horizon_min)
        return frac * p + (1.0 - frac) * float(self.w2(row))

    def predict_one(self, row: dict) -> float:
        raw = self._raw(row)
        return self.cal.transform_one(raw) if (self.cal is not None and self.cal.fitted) else raw

    @property
    def have_head(self) -> bool:
        return self.head is not None


class SelectiveHorizonGate:
    """research.horizon.selective_gate_h4 -- selective gate over {h0..h3} for one horizon.

    On TRAIN (via internal completeness banding identical in spirit to the W/D/L selective gate) the gate
    chooses, per completeness band, WHICH horizon head to trust: the W2-implied baseline (h0), or the
    richest head whose evidence the row supports. Low completeness -> h0 (pure W2-implied fallback,
    always reachable). The chosen mapping is frozen; predict routes by the row's completeness. Falls back
    to h0 everywhere when no event-process head beats h0 on TRAIN."""

    COMPLETENESS_BANDS = (0.40, 0.75)

    def __init__(self, horizon_min: int, candidate_cols: Optional[Sequence[str]] = None):
        self.horizon_min = int(horizon_min)
        self.candidate_cols = candidate_cols
        self.h0 = horizon_w2_implied_h0(horizon_min)
        self.heads: Dict[str, HorizonHazard] = {}
        self.band_choice: Dict[str, str] = {"low": "h0", "mid": "h0", "high": "h0"}
        self.fit_diagnostics: Dict[str, object] = {}

    def _band(self, row: dict) -> str:
        c = row.get("ri_completeness")
        if c is None:
            c = AV.row_completeness(row, F.ALL_FEATURE_COLS)
        c = float(c)
        lo, hi = self.COMPLETENESS_BANDS
        return "high" if c >= hi else ("mid" if c >= lo else "low")

    def _candidate_for(self, name: str, row: dict) -> float:
        if name == "h0":
            return float(self.h0(row))
        return float(self.heads[name].predict_one(row))

    def fit(self, train_rows: Sequence[dict]) -> "SelectiveHorizonGate":
        rows = list(train_rows)
        AV.annotate_completeness(rows, F.ALL_FEATURE_COLS)
        for name, fams in _HORIZON_FAMILIES.items():
            self.heads[name] = HorizonHazard(self.horizon_min, fams, self.candidate_cols).fit(rows)
        key = _target_key(self.horizon_min)
        labelled = [r for r in rows if r.get(key) is not None and str(r.get(key)) != ""
                    and _observable_fraction(r, self.horizon_min) >= 0.999]
        names = ["h0"] + list(self._HORIZON_ORDER)
        for band in ("low", "mid", "high"):
            band_rows = [r for r in labelled if self._band(r) == band]
            if len(band_rows) < 30:
                self.band_choice[band] = "h0"
                continue
            best_name, best_ll = "h0", self._mean_logloss("h0", band_rows, key)
            # low band ALWAYS defers to h0 (never raise confidence on sparse evidence)
            search = ["h0"] if band == "low" else names
            for name in search:
                ll = self._mean_logloss(name, band_rows, key)
                if ll is not None and ll < best_ll - 1e-12:
                    best_ll, best_name = ll, name
            self.band_choice[band] = best_name
        self.fit_diagnostics = {
            "horizon_min": self.horizon_min, "band_choice": dict(self.band_choice),
            "bands": list(self.COMPLETENESS_BANDS),
            "heads_available": {n: h.have_head for n, h in self.heads.items()},
            "degenerate_h0_everywhere": all(v == "h0" for v in self.band_choice.values()),
        }
        return self

    _HORIZON_ORDER = ("h1", "h2", "h3")

    def _mean_logloss(self, name: str, rows: Sequence[dict], key: str) -> Optional[float]:
        if not rows:
            return None
        tot = 0.0
        for r in rows:
            p = min(1 - 1e-9, max(1e-9, self._candidate_for(name, r)))
            y = int(float(r[key]))
            tot += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        return tot / len(rows)

    def predict_one(self, row: dict) -> float:
        return self._candidate_for(self.band_choice[self._band(row)], row)


def horizon_predictors(train_rows: Sequence[dict], horizon_min: int
                       ) -> Dict[str, Callable[[dict], float]]:
    """Build the near-term HORIZON family {h0, h1, h2, h3, h4} for a single horizon (5/10/15 min) as
    TRAIN-fit P(any goal in window) callables. h0 is the W2-implied baseline; h1..h3 are event-process
    competing-risk hazards; h4 selectively gates them (alpha=0/h0 fallback always reachable). Each is a
    leakage-safe, right-censored hazard for THIS horizon only."""
    preds: Dict[str, Callable[[dict], float]] = {}
    preds[assert_canonical("research.horizon.w2_implied_h0")] = horizon_w2_implied_h0(horizon_min)
    preds[assert_canonical("research.horizon.xg_residual_h1")] = \
        HorizonHazard(horizon_min, _HORIZON_FAMILIES["h1"]).fit(train_rows).predict_one
    preds[assert_canonical("research.horizon.possession_transition_h2")] = \
        HorizonHazard(horizon_min, _HORIZON_FAMILIES["h2"]).fit(train_rows).predict_one
    preds[assert_canonical("research.horizon.full_event_process_h3")] = \
        HorizonHazard(horizon_min, _HORIZON_FAMILIES["h3"]).fit(train_rows).predict_one
    preds[assert_canonical("research.horizon.selective_gate_h4")] = \
        SelectiveHorizonGate(horizon_min).fit(train_rows).predict_one
    return preds


__all__ = [
    "MODELS_VERSION", "ARTIFACT_LABELS", "HORIZONS",
    # intensity
    "build_event_residual_home_away_i1", "RegimeSpecificIntensity", "build_regime_specific_i2",
    "ClubTransferIntensity", "build_club_transfer_i3", "intensity_predictors",
    # residual W/D/L
    "CompetingRiskWDL", "build_competing_risk_r2", "residual_predictors",
    # near-term horizon
    "horizon_w2_implied_h0", "HorizonHazard", "SelectiveHorizonGate", "horizon_predictors",
    # re-exported anchors / builders
    "w2_reference_r0", "w2_home_away_i0", "w2_implied_h0",
]
