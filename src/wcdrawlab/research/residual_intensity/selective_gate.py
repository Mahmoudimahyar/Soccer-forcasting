"""Selective-correction GATE.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

The gate decides, per row, HOW MUCH of the event-process correction to apply on top of the W2
reference (r0/i0). Three decisions:

    fallback_to_w2            -> alpha = 0.0           (pure W2 reference; the honest default)
    apply_low_weight_correction -> alpha = alpha_low   (partial correction)
    apply_full_correction     -> alpha = alpha_full     (full event-process correction)

DESIGN INVARIANTS (spec):
  * alpha = 0 MUST be reachable: when evidence is insufficient the gate falls back to W2 entirely.
  * Thresholds are chosen ONLY on TRAINING data (fit) and frozen for predict; no test row, no test
    label ever influences a threshold.
  * The gate uses ONLY causal availability/state fields (event-process completeness, xG presence,
    regime). It NEVER raises confidence (never increases alpha) when completeness is LOW -- completeness
    is monotonically tied to the correction weight, so a sparser row can only get a smaller alpha.
  * If, on TRAIN, the full correction does not beat the W2 reference (by the configured score), the gate
    degenerates to alpha=0 everywhere (i.e. it selects pure fallback) -- the model never corrects when
    correction is not earned in-train.

The blend itself is a fixed convex form:  p = (1 - alpha) * p_w2 + alpha * p_correction  (per class,
renormalized). The gate only chooses alpha; it does not learn the blend coefficients beyond the
in-train selection of {alpha_low, alpha_full} from a small predeclared grid.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

from . import availability as AV
from . import features as F
from . import regimes as RG

GATE_VERSION = "residual_intensity_selective_gate_v1"
WDL = ["H", "D", "A"]
EPS = 1e-12

# predeclared alpha grids (NO test-tuning; chosen in-train by the configured score)
ALPHA_LOW_GRID = [0.0, 0.25, 0.5]
ALPHA_FULL_GRID = [0.0, 0.5, 0.75, 1.0]
# predeclared completeness thresholds the gate may select between (training-chosen)
COMPLETENESS_GRID = [(0.40, 0.75), (0.50, 0.80), (0.60, 0.85)]


def _blend(p_w2: Dict[str, float], p_corr: Dict[str, float], alpha: float) -> Dict[str, float]:
    """Convex per-class blend, renormalized. alpha=0 -> pure W2; alpha=1 -> pure correction."""
    a = max(0.0, min(1.0, float(alpha)))
    out = {k: (1.0 - a) * float(p_w2.get(k, 0.0)) + a * float(p_corr.get(k, 0.0)) for k in WDL}
    s = sum(out.values())
    if s <= 0:
        return {k: 1.0 / len(WDL) for k in WDL}
    return {k: v / s for k, v in out.items()}


def _logloss(p: Dict[str, float], y: str) -> float:
    import math
    return -math.log(max(EPS, float(p.get(y, 0.0))))


class SelectiveGate:
    """Selects, on TRAIN only, completeness thresholds + {alpha_low, alpha_full} that minimize mean
    log-loss of the blended prediction vs the pure-W2 reference. Frozen for predict. alpha=0 always
    permitted; degenerates to pure fallback when correction is not earned in-train."""

    def __init__(self, candidate_cols: Optional[Sequence[str]] = None,
                 alpha_low_grid: Sequence[float] = ALPHA_LOW_GRID,
                 alpha_full_grid: Sequence[float] = ALPHA_FULL_GRID,
                 completeness_grid: Sequence = COMPLETENESS_GRID):
        self.candidate_cols = list(candidate_cols) if candidate_cols is not None else list(F.ALL_FEATURE_COLS)
        self.alpha_low_grid = list(alpha_low_grid)
        self.alpha_full_grid = list(alpha_full_grid)
        self.completeness_grid = list(completeness_grid)
        # frozen, set by fit():
        self.t_low: float = 0.40
        self.t_full: float = 0.75
        self.alpha_low: float = 0.0
        self.alpha_full: float = 0.0
        self.fitted: bool = False
        self.fit_diagnostics: Dict[str, object] = {}

    # ---- per-row completeness (causal availability only) -----------------------------------------
    def completeness(self, row: dict) -> float:
        c = row.get("ri_completeness")
        if c is not None:
            try:
                return float(c)
            except (TypeError, ValueError):
                pass
        return AV.row_completeness(row, self.candidate_cols)

    def decision(self, row: dict) -> str:
        """fallback_to_w2 / apply_low_weight_correction / apply_full_correction -- by completeness only.
        Lower completeness can only map to a LOWER-correction band (never raises confidence)."""
        c = self.completeness(row)
        if c >= self.t_full:
            return "apply_full_correction"
        if c >= self.t_low:
            return "apply_low_weight_correction"
        return "fallback_to_w2"

    def alpha_for(self, row: dict) -> float:
        d = self.decision(row)
        if d == "apply_full_correction":
            return self.alpha_full
        if d == "apply_low_weight_correction":
            return self.alpha_low
        return 0.0

    # ---- in-train selection ----------------------------------------------------------------------
    def fit(self, train_rows: Sequence[dict],
            p_w2: Callable[[dict], Dict[str, float]],
            p_corr: Callable[[dict], Dict[str, float]],
            target_key: str = "target_wdl") -> "SelectiveGate":
        """Choose (t_low, t_full, alpha_low, alpha_full) minimizing mean train log-loss of the gated
        blend. Baseline = pure W2 (all alpha=0). If no configuration beats W2 on TRAIN, the gate keeps
        alpha_low=alpha_full=0 (pure fallback). Uses ONLY train labels; deterministic grid search."""
        rows = [r for r in train_rows if r.get(target_key) in WDL]
        if not rows:
            self.fitted = True
            self.fit_diagnostics = {"reason": "no_train_labels", "alpha_low": 0.0, "alpha_full": 0.0}
            return self
        # cache reference / correction probs + completeness once per row (deterministic)
        cache = []
        for r in rows:
            cache.append((self.completeness(r), p_w2(r), p_corr(r), r[target_key]))

        base_ll = sum(_logloss(pw2, y) for (_, pw2, _, y) in cache) / len(cache)

        best = {"ll": base_ll, "t_low": self.t_low, "t_full": self.t_full,
                "alpha_low": 0.0, "alpha_full": 0.0}
        for (t_low, t_full) in self.completeness_grid:
            for a_low in self.alpha_low_grid:
                for a_full in self.alpha_full_grid:
                    # enforce monotonicity: full-band correction must be >= low-band correction
                    if a_full < a_low:
                        continue
                    tot = 0.0
                    for (comp, pw2, pcorr, y) in cache:
                        if comp >= t_full:
                            a = a_full
                        elif comp >= t_low:
                            a = a_low
                        else:
                            a = 0.0
                        tot += _logloss(_blend(pw2, pcorr, a), y)
                    ll = tot / len(cache)
                    if ll < best["ll"] - 1e-12:
                        best = {"ll": ll, "t_low": t_low, "t_full": t_full,
                                "alpha_low": a_low, "alpha_full": a_full}
        self.t_low = best["t_low"]; self.t_full = best["t_full"]
        self.alpha_low = best["alpha_low"]; self.alpha_full = best["alpha_full"]
        self.fitted = True
        # correction coverage = fraction of TRAIN rows that receive any correction (alpha>0)
        corrected = sum(1 for (comp, _, _, _) in cache
                        if (comp >= self.t_full and self.alpha_full > 0)
                        or (self.t_low <= comp < self.t_full and self.alpha_low > 0))
        self.fit_diagnostics = {
            "baseline_w2_logloss": round(base_ll, 6),
            "gated_train_logloss": round(best["ll"], 6),
            "t_low": self.t_low, "t_full": self.t_full,
            "alpha_low": self.alpha_low, "alpha_full": self.alpha_full,
            "correction_coverage_train": round(corrected / len(cache), 6),
            "degenerate_fallback": bool(self.alpha_low == 0.0 and self.alpha_full == 0.0),
        }
        return self

    # ---- HONEST in-train selection via internal held-out folds ------------------------------------
    def fit_cv(self, train_rows: Sequence[dict],
               p_w2: Callable[[dict], Dict[str, float]],
               correction_factory: Callable[[Sequence[dict]], Callable[[dict], Dict[str, float]]],
               fold_key: str = "competition",
               target_key: str = "target_wdl") -> "SelectiveGate":
        """Choose (t_low, t_full, alpha_low, alpha_full) by scoring each candidate config on rows that
        were HELD OUT of the correction model's own training -- the honest version of "alpha chosen
        in-train". The correction is refit on each internal-train slice and scored on the held-out
        internal slice, so the gate sees the true generalization gap and degenerates to alpha=0 when the
        correction does not generalize (rather than over-trusting an in-sample fit). Splits use
        leave-one-group-out over ``fold_key`` (competition) within TRAIN; falls back to a deterministic
        2-way split when only one group is present. Uses ONLY train labels; deterministic."""
        labelled = [r for r in train_rows if r.get(target_key) in WDL]
        if not labelled:
            self.fitted = True
            self.fit_diagnostics = {"reason": "no_train_labels", "alpha_low": 0.0, "alpha_full": 0.0,
                                    "method": "cv"}
            return self

        groups = sorted({r.get(fold_key) for r in labelled if r.get(fold_key) is not None})
        if len(groups) >= 2:
            splits = [( [r for r in labelled if r.get(fold_key) != g],
                        [r for r in labelled if r.get(fold_key) == g] ) for g in groups]
        else:
            mid = max(1, len(labelled) // 2)
            splits = [(labelled[:mid], labelled[mid:]), (labelled[mid:], labelled[:mid])]

        # collect out-of-internal-fold (completeness, p_w2, p_corr_oof, y) tuples
        cache = []
        for tr, va in splits:
            if not tr or not va:
                continue
            corr_oof = correction_factory(tr)  # refit correction on internal-train ONLY
            for r in va:
                cache.append((self.completeness(r), p_w2(r), corr_oof(r), r[target_key]))
        if not cache:  # degenerate; keep pure fallback
            self.fitted = True
            self.alpha_low = self.alpha_full = 0.0
            self.fit_diagnostics = {"reason": "no_internal_folds", "alpha_low": 0.0, "alpha_full": 0.0,
                                    "method": "cv"}
            return self

        base_ll = sum(_logloss(pw2, y) for (_, pw2, _, y) in cache) / len(cache)
        best = {"ll": base_ll, "t_low": self.t_low, "t_full": self.t_full,
                "alpha_low": 0.0, "alpha_full": 0.0}
        for (t_low, t_full) in self.completeness_grid:
            for a_low in self.alpha_low_grid:
                for a_full in self.alpha_full_grid:
                    if a_full < a_low:
                        continue
                    tot = 0.0
                    for (comp, pw2, pcorr, y) in cache:
                        a = a_full if comp >= t_full else (a_low if comp >= t_low else 0.0)
                        tot += _logloss(_blend(pw2, pcorr, a), y)
                    ll = tot / len(cache)
                    if ll < best["ll"] - 1e-12:
                        best = {"ll": ll, "t_low": t_low, "t_full": t_full,
                                "alpha_low": a_low, "alpha_full": a_full}
        self.t_low = best["t_low"]; self.t_full = best["t_full"]
        self.alpha_low = best["alpha_low"]; self.alpha_full = best["alpha_full"]
        self.fitted = True
        corrected = sum(1 for (comp, _, _, _) in cache
                        if (comp >= self.t_full and self.alpha_full > 0)
                        or (self.t_low <= comp < self.t_full and self.alpha_low > 0))
        self.fit_diagnostics = {
            "method": "cv_internal_folds",
            "n_internal_folds": len(splits),
            "baseline_w2_oof_logloss": round(base_ll, 6),
            "gated_oof_logloss": round(best["ll"], 6),
            "t_low": self.t_low, "t_full": self.t_full,
            "alpha_low": self.alpha_low, "alpha_full": self.alpha_full,
            "correction_coverage_oof": round(corrected / len(cache), 6),
            "degenerate_fallback": bool(self.alpha_low == 0.0 and self.alpha_full == 0.0),
        }
        return self

    # ---- predict ---------------------------------------------------------------------------------
    def predict_one(self, row: dict,
                    p_w2: Callable[[dict], Dict[str, float]],
                    p_corr: Callable[[dict], Dict[str, float]]) -> Dict[str, float]:
        a = self.alpha_for(row)
        if a <= 0.0:
            return p_w2(row)
        return _blend(p_w2(row), p_corr(row), a)
