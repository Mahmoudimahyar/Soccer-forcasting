"""Event-process MODEL FAMILIES (event-process intelligence phase).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

EXTENDS ``wcdrawlab.research.dynamic_models`` (imported as ``DM``): reuses the exact regularized fitters
(RidgeLogitMulti / RidgeLogitBin), the graceful-unknown FeatureSpace (TRAIN-mean impute + ``__unknown``
indicator), the deterministic internal-CV C selection, the IsotonicCalibrator, and the parameter-free
remaining-time Poisson reference. Nothing here re-implements a fitter; each new family is a column-set
plus a fixed, preregistered combination rule.

W/D/L via GOAL-INTENSITY (the spec mandates this, NOT a direct multinomial on the label):
    An intensity model estimates home/away *remaining-goal intensities* (lam_h, lam_a) from the causal
    in-play event-process state at the decision minute. The remaining-score distribution is the
    independent-Poisson convolution of (lam_h, lam_a); it is combined with the CURRENT regulation score
    and remaining time to give P(final H / D / A). A monotone per-channel calibrator (DM.IsotonicCalibrator)
    is fit INSIDE the training fold only and frozen for predict -- it never consults a test label.

Canonical model IDs (verbatim from registry.py; NEVER M1-M5):

  research.event_process.e0   static anchor      -- TRAIN base-rate W/D/L (no event-process info)
  research.event_process.e1   time + score       -- DM r1 (minute + current score-state logistic)
  research.event_process.e2   remaining-time Poisson reference -- parameter-free; the CANDIDATE REFERENCE
  research.event_process.e3   xG intensity       -- intensity from cumulative + rolling xG / shots
  research.event_process.e4   possession + territory intensity
  research.event_process.e5   transition + pressure intensity
  research.event_process.e6   set-piece + discipline intensity
  research.event_process.e7   full event-process state intensity
  research.event_process.e8   e7 + auxiliary CLUB transfer representation (club rows train the rep ONLY)
  research.event_process.e9   calibrated hybrid  -- fixed blend of {e2, e3, e7} + in-train calibration

  research.next_goal.q0..q4   next-goal hazard (binary: a regulation goal by either side in next 15')
  research.scoring.h0..h3     near-term scoring (binary: any goal in the next 10')
  research.discipline.y0..y2  discipline hazard (binary: a sending-off strictly after t; gated on positives)

Leakage / honesty contract (inherited + enforced):
  * Features at decision minute t use ONLY snapshot columns already truncated to elapsed <= t upstream.
  * No final score, no post-decision totals; regulation only (period<=2, minute<=90); no ET/shootout.
  * Club rows may TRAIN the e8 auxiliary representation but are NEVER intl test rows (enforced in eval.py).
  * Missing source fields are imputed on TRAIN means + flagged with a companion ``__unknown`` indicator
    (DM.FeatureSpace), never silently imputed as 0; an all-missing row collapses to the anchor.
  * The remaining-time intensity reference (e2) is parameter-free and is what every candidate must beat.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from wcdrawlab.research import dynamic_models as DM  # reuse fitters / FeatureSpace / calibrator / Poisson
from wcdrawlab.research.event_process import registry as REG

MODEL_VERSION = "event_process_models_v1"
WDL = ["H", "D", "A"]
EPS = 1e-9

# Goals-per-team-per-90' reference rate for the parameter-free remaining-time intensity (e2).
# Identical to DM.R2_BASE, so e2 here is the remaining-time Poisson reference (NOT the frozen M2).
BASE_RATE_PER90 = DM.R2_BASE  # 1.35


# ====================================================================================================
# Snapshot column groups (mirror the intl/club event-process snapshot schema). Each model degrades
# gracefully when a column is absent (DM.FeatureSpace imputes TRAIN-mean + sets <col>__unknown).
# ====================================================================================================
STATE_COLS = ["goals_diff", "remaining_regulation_min", "snapshot_minute"]

# e3: xG intensity (cumulative + rolling momentum + shot volume).
XG_INTENSITY_COLS = [
    "cum_xg_home", "cum_xg_away", "cum_xg_diff",
    "xg_last5m_home", "xg_last5m_away", "xg_last10m_home", "xg_last10m_away",
    "xg_momentum_diff_10m", "xg_acceleration_diff",
    "shots_home", "shots_away", "shots_on_target_home", "shots_on_target_away",
]

# e4: possession + territory.
POSS_TERRITORY_COLS = [
    "poss_share_home", "poss_share_diff", "field_tilt_home",
    "final_third_actions_home", "final_third_actions_away", "final_third_actions_diff",
    "box_entries_home", "box_entries_away", "box_entries_diff",
]

# e5: transition + pressure (recoveries / turnovers as progression / disruption proxies).
TRANSITION_PRESSURE_COLS = [
    "recoveries_home", "recoveries_away", "recoveries_diff",
    "turnovers_home", "turnovers_away", "turnovers_diff",
    "min_since_last_shot_home", "min_since_last_shot_away", "min_since_major_chance",
]

# e6: set-piece + discipline.
SETPIECE_DISCIPLINE_COLS = [
    "corners_home", "corners_away", "corners_diff",
    "att_free_kicks_home", "att_free_kicks_away", "att_free_kicks_diff",
    "yellow_diff", "sendoff_diff", "players_diff", "subs_used_diff",
]

# e7 full state = union of e3..e6 + raw shot intensity context.
FULL_STATE_COLS = list(dict.fromkeys(
    XG_INTENSITY_COLS + POSS_TERRITORY_COLS + TRANSITION_PRESSURE_COLS + SETPIECE_DISCIPLINE_COLS
    + ["shots_diff", "shots_on_target_diff", "min_since_last_shot_any"]
))

# e8 auxiliary club representation column set (provider-neutral process state shared club<->intl).
AUX_REP_COLS = list(dict.fromkeys(
    XG_INTENSITY_COLS + POSS_TERRITORY_COLS + TRANSITION_PRESSURE_COLS
))

# next-goal hazard columns.
NEXTGOAL_COLS = [
    "goals_diff", "remaining_regulation_min", "snapshot_minute",
    "xg_last5m_diff", "xg_last10m_diff", "xg_momentum_diff_10m",
    "shots_diff", "shots_on_target_diff", "box_entries_diff",
    "poss_share_diff", "min_since_last_shot_any",
]

# near-term scoring (any goal in horizon).
SCORING_COLS = [
    "goals_diff", "remaining_regulation_min",
    "cum_xg_total", "xg_last5m_home", "xg_last5m_away", "xg_last10m_home", "xg_last10m_away",
    "shots_home", "shots_away", "box_entries_diff", "min_since_last_shot_any",
]

# discipline hazard columns.
DISCIPLINE_COLS = [
    "yellow_home", "yellow_away", "yellow_diff", "sendoff_diff",
    "att_free_kicks_diff", "turnovers_diff", "goals_diff", "remaining_regulation_min",
]


# ====================================================================================================
# Helpers
# ====================================================================================================
def _norm(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(d.values()) or 1.0
    return {k: v / s for k, v in d.items()}


def _f(row: dict, col: str, default: float = 0.0) -> float:
    v = row.get(col, default)
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(x) or math.isinf(x):
        return default
    return x


def _remaining_fraction(row: dict) -> float:
    """Fraction of regulation still to play, in [0, 1]. Prefers the explicit remaining-minutes column."""
    rem = row.get("remaining_regulation_min", None)
    if rem is None:
        rem = row.get("remaining", None)
    if rem is None:
        mn = _f(row, "snapshot_minute", _f(row, "minute", 0.0))
        rem = max(0.0, 90.0 - mn)
    try:
        rem = float(rem)
    except (TypeError, ValueError):
        rem = 0.0
    if math.isnan(rem) or math.isinf(rem):
        rem = 0.0
    return max(0.0, min(1.0, rem / 90.0))


def _current_diff(row: dict) -> int:
    d = row.get("goals_diff", row.get("score_diff", 0))
    try:
        return int(round(float(d)))
    except (TypeError, ValueError):
        return 0


# ====================================================================================================
# Goal-intensity -> remaining-score distribution -> P(final H/D/A)
# ====================================================================================================
def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def wdl_from_intensities(lam_h: float, lam_a: float, current_diff: int,
                         kmax: int = 8) -> Dict[str, float]:
    """Independent-Poisson remaining-goal convolution combined with the CURRENT score diff.

    lam_h / lam_a are the expected REMAINING regulation goals for home / away; current_diff is the
    present regulation (home - away) goal difference. Returns P(final H / D / A) (pre-calibration).
    """
    lam_h = max(0.0, float(lam_h))
    lam_a = max(0.0, float(lam_a))
    pmf_h = [_poisson_pmf(k, lam_h) for k in range(kmax + 1)]
    pmf_a = [_poisson_pmf(k, lam_a) for k in range(kmax + 1)]
    pH = pD = pA = 0.0
    for fh in range(kmax + 1):
        ph = pmf_h[fh]
        for fa in range(kmax + 1):
            p = ph * pmf_a[fa]
            d = current_diff + fh - fa
            if d > 0:
                pH += p
            elif d == 0:
                pD += p
            else:
                pA += p
    return _norm({"H": pH, "D": pD, "A": pA})


def e2_reference(row: dict) -> Dict[str, float]:
    """e2 -- parameter-free remaining-time Poisson reference (the candidate REFERENCE model).

    Both teams share the league base intensity scaled by remaining time, combined with the current score
    diff. This is the event-process analogue of DM.r2 and is what every candidate must beat.
    """
    frac = _remaining_fraction(row)
    lam = BASE_RATE_PER90 * frac
    return wdl_from_intensities(lam, lam, _current_diff(row))


# ====================================================================================================
# _RidgeLinear: deterministic closed-form ridge regression on a DM.FeatureSpace. Used as the
# log-intensity head (predicting side-specific remaining goals), NOT a label regressor.
# ====================================================================================================
class _RidgeLinear:
    """Deterministic ridge linear regression (closed form) on standardized features. TRAIN-only fit."""

    def __init__(self, space: "DM.FeatureSpace", l2: float = 1.0):
        self.space = space
        self.l2 = l2
        self.w: Optional[np.ndarray] = None
        self.mean: Optional[np.ndarray] = None
        self.std: Optional[np.ndarray] = None
        self.y_mean: float = 0.0

    def fit(self, train_rows: Sequence[dict], y: Sequence[float]) -> "_RidgeLinear":
        self.space.fit(train_rows)
        X = self.space.matrix(train_rows)
        yv = np.asarray(y, dtype=float)
        self.y_mean = float(np.mean(yv)) if len(yv) else 0.0
        if X.shape[0] == 0 or X.shape[1] == 0:
            self.w = None
            return self
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        self.std[self.std < 1e-9] = 1.0
        Xs = (X - self.mean) / self.std
        Xb = np.hstack([Xs, np.ones((Xs.shape[0], 1))])
        d = Xb.shape[1]
        pen = np.eye(d) * self.l2
        pen[-1, -1] = 0.0  # no penalty on intercept
        try:
            self.w = np.linalg.solve(Xb.T @ Xb + pen, Xb.T @ yv)
        except np.linalg.LinAlgError:
            self.w = np.linalg.lstsq(Xb.T @ Xb + pen, Xb.T @ yv, rcond=None)[0]
        return self

    def predict_one(self, row: dict) -> float:
        if self.w is None or self.mean is None:
            return self.y_mean
        x = np.asarray(self.space.row_vector(row), dtype=float)
        xs = (x - self.mean) / self.std
        xb = np.append(xs, 1.0)
        return float(xb @ self.w)


# ====================================================================================================
# IntensityWDL: side-specific remaining-goal intensity -> WDL via Poisson convolution + in-train cal.
# ====================================================================================================
class IntensityWDL:
    """Side-specific remaining-goal intensity model -> WDL via Poisson convolution + in-train calibration.

    Fits two ridge regressions predicting log(1 + remaining goals) for home / away from the causal
    in-play state, using TRAIN rows where the side-specific remaining-goal counts are known
    (``rem_goals_home`` / ``rem_goals_away``, attached by the eval loader). Predict: expm1(.) clamped >=0
    gives lam_h / lam_a; convolve with the current diff; then apply a frozen per-channel isotonic
    calibrator fit on TRAIN pooled-vs-outcome so the WDL probabilities are calibrated without consulting
    any test label. If the side-specific targets are absent, it falls back to the e2 reference (so the
    family degrades honestly rather than crashing).
    """

    def __init__(self, cols: Sequence[str], with_anchor: bool = True, l2: float = 1.0):
        self.cols = list(cols)
        self.with_anchor = with_anchor
        self.l2 = l2
        self.mh: Optional[_RidgeLinear] = None
        self.ma: Optional[_RidgeLinear] = None
        self.cal: Dict[str, DM.IsotonicCalibrator] = {}
        self.have_heads = False

    def _space(self) -> "DM.FeatureSpace":
        return DM.FeatureSpace(self.cols, with_r2_anchor=self.with_anchor)

    def _raw_intensities(self, row: dict) -> "tuple[float, float]":
        if not self.have_heads:
            lam = BASE_RATE_PER90 * _remaining_fraction(row)
            return lam, lam
        lh = max(0.0, math.expm1(self.mh.predict_one(row)))
        la = max(0.0, math.expm1(self.ma.predict_one(row)))
        return lh, la

    def _raw_wdl(self, row: dict) -> Dict[str, float]:
        lh, la = self._raw_intensities(row)
        return wdl_from_intensities(lh, la, _current_diff(row))

    def fit(self, train_rows: Sequence[dict], target_key: str = "target_wdl") -> "IntensityWDL":
        usable = [r for r in train_rows
                  if r.get("rem_goals_home") is not None and r.get("rem_goals_away") is not None]
        if usable:
            yh = [math.log1p(max(0.0, _f(r, "rem_goals_home"))) for r in usable]
            ya = [math.log1p(max(0.0, _f(r, "rem_goals_away"))) for r in usable]
            self.mh = _RidgeLinear(self._space(), self.l2).fit(usable, yh)
            self.ma = _RidgeLinear(self._space(), self.l2).fit(usable, ya)
            self.have_heads = True
        cal_rows = [r for r in train_rows if r.get(target_key) in WDL]
        if cal_rows:
            pooled = [self._raw_wdl(r) for r in cal_rows]
            y = [r[target_key] for r in cal_rows]
            for k in WDL:
                pk = np.array([pp[k] for pp in pooled])
                yk = np.array([1.0 if t == k else 0.0 for t in y])
                self.cal[k] = DM.IsotonicCalibrator().fit(pk, yk)
        return self

    def predict_one(self, row: dict) -> Dict[str, float]:
        raw = self._raw_wdl(row)
        if not self.cal:
            return raw
        out = {}
        for k in WDL:
            c = self.cal.get(k)
            out[k] = float(c.transform(np.array([raw[k]]))[0]) if c is not None else raw[k]
        return _norm(out)


# ====================================================================================================
# e8 auxiliary CLUB transfer representation.
# A compact intensity-difference rep is trained on CLUB rows only and applied to intl rows as one extra
# scalar feature. Club rows NEVER enter the intl train/test split; only this frozen mapping crosses over.
# ====================================================================================================
class ClubAuxRep:
    """Frozen scalar event-process representation learned from CLUB rows: predicted remaining
    goal-difference intensity (rem_goals_home - rem_goals_away) from the provider-neutral event state.
    Applied to intl rows as ``aux_club_intensity_diff``. Never trained/calibrated on intl test rows."""

    def __init__(self, cols: Sequence[str] = AUX_REP_COLS, l2: float = 2.0):
        self.cols = list(cols)
        self.l2 = l2
        self.model: Optional[_RidgeLinear] = None
        self.trained_on_club_rows: int = 0

    def fit(self, club_rows: Sequence[dict]) -> "ClubAuxRep":
        usable = [r for r in club_rows
                  if r.get("comp_type", "club") == "club"
                  and r.get("rem_goals_home") is not None and r.get("rem_goals_away") is not None]
        self.trained_on_club_rows = len(usable)
        if usable:
            y = [(_f(r, "rem_goals_home") - _f(r, "rem_goals_away")) for r in usable]
            self.model = _RidgeLinear(DM.FeatureSpace(self.cols, with_r2_anchor=False), self.l2).fit(usable, y)
        return self

    def value(self, row: dict) -> float:
        return float(self.model.predict_one(row)) if self.model is not None else 0.0

    def annotate(self, rows: Sequence[dict]) -> None:
        """Attach the frozen aux value in-place as ``aux_club_intensity_diff`` (0.0 when unavailable)."""
        for r in rows:
            r["aux_club_intensity_diff"] = self.value(r)


# ====================================================================================================
# e9 calibrated hybrid: fixed-form geometric pool of {e2, e3, e7} with in-train per-channel calibration.
# Reuses DM.CalibratedBlend (blend FORM fixed; only the monotone calibrators are fit, on TRAIN).
# ====================================================================================================
def _hybrid_components(train_rows: Sequence[dict]) -> List[Callable[[dict], Dict[str, float]]]:
    e3 = IntensityWDL(XG_INTENSITY_COLS).fit(train_rows)
    e7 = IntensityWDL(FULL_STATE_COLS).fit(train_rows)
    return [e2_reference, e3.predict_one, e7.predict_one]


# ====================================================================================================
# Public family factories. Each returns {canonical_id: predict(row)->probs|float}, fit on TRAIN only.
# club_rows (optional) train ONLY the e8 auxiliary representation.
# ====================================================================================================
def event_process_predictors(train_rows: Sequence[dict],
                             club_rows: Optional[Sequence[dict]] = None,
                             target_key: str = "target_wdl",
                             include_club_transfer: bool = True) -> Dict[str, Callable]:
    """W/D/L event-process family e0..e9 (goal-intensity). e2 is the parameter-free reference.

    e8 reads a frozen CLUB auxiliary representation when ``club_rows`` are supplied and
    ``include_club_transfer`` is True; otherwise e8 degrades to e7's column set (this is the
    with/without-club-transfer comparison the spec requires)."""
    br = DM._base_rate(train_rows, target_key, WDL)              # e0 static anchor
    e1 = DM._r1_predictor(train_rows)                            # e1 time + score (DM r1)
    e3 = IntensityWDL(XG_INTENSITY_COLS).fit(train_rows, target_key)
    e4 = IntensityWDL(POSS_TERRITORY_COLS).fit(train_rows, target_key)
    e5 = IntensityWDL(TRANSITION_PRESSURE_COLS).fit(train_rows, target_key)
    e6 = IntensityWDL(SETPIECE_DISCIPLINE_COLS).fit(train_rows, target_key)
    e7 = IntensityWDL(FULL_STATE_COLS).fit(train_rows, target_key)

    # e8: e7 columns + frozen club aux rep (trained on club rows only; never on intl test rows)
    aux: Optional[ClubAuxRep] = None
    e8_cols = list(FULL_STATE_COLS)
    if include_club_transfer and club_rows:
        aux = ClubAuxRep().fit(club_rows)
        if aux.trained_on_club_rows > 0:
            aux.annotate(train_rows)  # annotate intl TRAIN rows with frozen aux value, then fit e8 with it
            e8_cols = FULL_STATE_COLS + ["aux_club_intensity_diff"]
    e8_model = IntensityWDL(e8_cols).fit(train_rows, target_key)

    def e8_predict(row: dict) -> Dict[str, float]:
        if aux is not None and aux.trained_on_club_rows > 0 and "aux_club_intensity_diff" not in row:
            row = dict(row)
            row["aux_club_intensity_diff"] = aux.value(row)
        return e8_model.predict_one(row)

    e9 = DM.CalibratedBlend(_hybrid_components(train_rows)).fit(train_rows, target_key)  # e9 hybrid

    preds = {
        "research.event_process.e0": lambda r: dict(br),
        "research.event_process.e1": e1,
        "research.event_process.e2": e2_reference,
        "research.event_process.e3": e3.predict_one,
        "research.event_process.e4": e4.predict_one,
        "research.event_process.e5": e5.predict_one,
        "research.event_process.e6": e6.predict_one,
        "research.event_process.e7": e7.predict_one,
        "research.event_process.e8": e8_predict,
        "research.event_process.e9": e9.predict_one,
    }
    for mid in preds:
        REG.assert_canonical(mid)
    return preds


def next_goal_predictors(train_rows: Sequence[dict],
                         target_key: str = "next_goal_any_15") -> Dict[str, Callable]:
    """Next-goal hazard family q0..q4 (binary: a regulation goal within the next 15'). Reuses
    DM.RidgeLogitBin for q1..q4; q0 is the TRAIN base rate."""
    base = float(np.mean([int(r.get(target_key, 0)) for r in train_rows])) if train_rows else 0.0
    q1 = DM.RidgeLogitBin(DM.FeatureSpace(["goals_diff", "remaining_regulation_min", "snapshot_minute"],
                                          with_r2_anchor=False)).fit(train_rows, target_key)
    q2 = DM.RidgeLogitBin(DM.FeatureSpace(NEXTGOAL_COLS[:7], with_r2_anchor=False)).fit(train_rows, target_key)
    q3 = DM.RidgeLogitBin(DM.FeatureSpace(NEXTGOAL_COLS, with_r2_anchor=False)).fit(train_rows, target_key)
    q4 = DM.RidgeLogitBin(DM.FeatureSpace(NEXTGOAL_COLS + ["xg_acceleration_diff", "field_tilt_home"],
                                          with_r2_anchor=False)).fit(train_rows, target_key)
    preds = {
        "research.next_goal.q0": lambda r: base,
        "research.next_goal.q1": q1.predict_one,
        "research.next_goal.q2": q2.predict_one,
        "research.next_goal.q3": q3.predict_one,
        "research.next_goal.q4": q4.predict_one,
    }
    for mid in preds:
        REG.assert_canonical(mid)
    return preds


def scoring_predictors(train_rows: Sequence[dict],
                       target_key: str = "any_goal_next10m") -> Dict[str, Callable]:
    """Near-term scoring family h0..h3 (binary: any goal in the next 10'). h0 base rate; h1..h3 add
    xG / shot / territory intensity. Reuses DM.RidgeLogitBin."""
    base = float(np.mean([int(r.get(target_key, 0)) for r in train_rows])) if train_rows else 0.0
    h1 = DM.RidgeLogitBin(DM.FeatureSpace(["goals_diff", "remaining_regulation_min", "cum_xg_total"],
                                          with_r2_anchor=False)).fit(train_rows, target_key)
    h2 = DM.RidgeLogitBin(DM.FeatureSpace(SCORING_COLS[:8], with_r2_anchor=False)).fit(train_rows, target_key)
    h3 = DM.RidgeLogitBin(DM.FeatureSpace(SCORING_COLS, with_r2_anchor=False)).fit(train_rows, target_key)
    preds = {
        "research.scoring.h0": lambda r: base,
        "research.scoring.h1": h1.predict_one,
        "research.scoring.h2": h2.predict_one,
        "research.scoring.h3": h3.predict_one,
    }
    for mid in preds:
        REG.assert_canonical(mid)
    return preds


DISCIPLINE_POSITIVE_GATE = 150


def discipline_predictors(train_rows: Sequence[dict],
                          target_key: str = "sendoff_after") -> Dict:
    """Discipline hazard family y0..y2. y0 = TRAIN base rate; y1/y2 (logistic hazards) are gated on
    >=150 positive TRAIN examples (preregistered; mirrors DM.discipline_predictors). Returns the
    predictors plus the gate diagnostics so eval can emit data_insufficient honestly when gated."""
    pos = int(sum(int(r.get(target_key, 0)) for r in train_rows))
    base = float(np.mean([int(r.get(target_key, 0)) for r in train_rows])) if train_rows else 0.0
    preds: Dict[str, Callable] = {"research.discipline.y0": (lambda r: base)}
    gate_open = pos >= DISCIPLINE_POSITIVE_GATE
    if gate_open:
        y1 = DM.RidgeLogitBin(DM.FeatureSpace(DISCIPLINE_COLS[:6], with_r2_anchor=False)).fit(train_rows, target_key)
        y2 = DM.RidgeLogitBin(DM.FeatureSpace(DISCIPLINE_COLS, with_r2_anchor=False)).fit(train_rows, target_key)
        preds["research.discipline.y1"] = y1.predict_one
        preds["research.discipline.y2"] = y2.predict_one
    for mid in preds:
        REG.assert_canonical(mid)
    return {"predictors": preds, "n_positives": pos, "gate_open": gate_open,
            "gate_threshold": DISCIPLINE_POSITIVE_GATE,
            "gated_status": "fit" if gate_open else "SKIPPED_below_gate"}


__all__ = [
    "MODEL_VERSION", "WDL", "BASE_RATE_PER90",
    "wdl_from_intensities", "e2_reference", "IntensityWDL", "ClubAuxRep",
    "event_process_predictors", "next_goal_predictors", "scoring_predictors", "discipline_predictors",
    "DISCIPLINE_POSITIVE_GATE",
    "STATE_COLS", "XG_INTENSITY_COLS", "POSS_TERRITORY_COLS", "TRANSITION_PRESSURE_COLS",
    "SETPIECE_DISCIPLINE_COLS", "FULL_STATE_COLS", "AUX_REP_COLS",
    "NEXTGOAL_COLS", "SCORING_COLS", "DISCIPLINE_COLS",
]
