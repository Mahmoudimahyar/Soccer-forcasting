"""Phase 2/4: silver-label abstention policy (R4) + preregistered release gate.

Thresholds are chosen ONLY on training-competition data. The release gate applies the FROZEN
preregistered criteria (see COMMENTARY_PRECISION_PREREGISTRATION.md). research_only / historical only.
"""
from __future__ import annotations

import math

# FROZEN preregistered thresholds
T1_MIN_PREDICTIONS = 50
T2_WILSON_LB = 0.80
T3_MEDIAN_TIMING_S = 15.0
T4_P90_TIMING_S = 35.0
T5_MIN_STABLE_FOLDS = 4
T5_MIN_FOLD_PREDS = 5
TRAIN_TARGET_PRECISION = 0.85   # train selection target (margin above the 0.80 test bar)


def wilson_lower_bound(k: int, n: int, z: float = 1.96) -> float:
    """Wilson score interval lower bound for a binomial proportion k/n."""
    if n == 0:
        return 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def select_threshold(scores, y, target_precision=TRAIN_TARGET_PRECISION, min_count=20):
    """Smallest confidence threshold (on TRAIN) whose emitted set reaches target precision with >= min_count
    emissions. Returns (threshold, train_precision, train_count). If none qualify, returns the strictest
    candidate (highest precision) so the policy errs toward abstention."""
    pairs = sorted(((s, yy) for s, yy in zip(scores, y) if s > 0), reverse=True)
    if not pairs:
        return 1.01, 0.0, 0
    best = None  # (threshold, prec, count) at highest precision seen with >=min_count
    k = n = 0
    qualifying = None
    for s, yy in pairs:
        n += 1
        k += yy
        prec = k / n
        if n >= min_count:
            if best is None or prec > best[1]:
                best = (s, prec, n)
            if prec >= target_precision:
                qualifying = (s, prec, n)  # keep extending while precision holds (max coverage at target)
    if qualifying is not None:
        return qualifying
    return best if best is not None else (1.01, pairs[0][1], 1)


def gate_class(n_pred, k_correct, median_timing, p90_timing, stable_folds, competitions_present):
    """Apply the FROZEN preregistered gate. Returns (label, reasons)."""
    reasons = []
    wlb = wilson_lower_bound(k_correct, n_pred)
    if n_pred < T1_MIN_PREDICTIONS:
        return "insufficient_coverage", [f"n_pred={n_pred} < {T1_MIN_PREDICTIONS}"]
    if competitions_present <= 1:
        return "insufficient_coverage", ["emitted from a single competition (T6)"]
    fails = []
    if wlb < T2_WILSON_LB:
        fails.append(f"WilsonLB={wlb:.3f} < {T2_WILSON_LB}")
    if median_timing is None or median_timing > T3_MEDIAN_TIMING_S:
        fails.append(f"median_timing={median_timing} > {T3_MEDIAN_TIMING_S}")
    if p90_timing is None or p90_timing > T4_P90_TIMING_S:
        fails.append(f"p90_timing={p90_timing} > {T4_P90_TIMING_S}")
    if stable_folds < T5_MIN_STABLE_FOLDS:
        fails.append(f"stable_folds={stable_folds} < {T5_MIN_STABLE_FOLDS}")
    if not fails:
        return "silver_label_approved_for_historical_research", [f"WilsonLB={wlb:.3f}", "all thresholds met"]
    # distinguish precision failure from low-confidence-usable
    if wlb < T2_WILSON_LB and (median_timing is not None and median_timing <= T3_MEDIAN_TIMING_S):
        if wlb >= 0.60:
            return "usable_only_with_low_confidence_flag", fails
        return "insufficient_precision", fails
    return "usable_only_with_low_confidence_flag", fails
