"""T6 / T7 — selective transfer (gated fallback) and its calibrated Monte-Carlo W/D/L view.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

  * ``T6SelectiveTransfer``  — wraps the domain-weighted partial-pooling intensity model (T5) but BLENDS
    it back toward the safe international-only model (T1), and ultimately toward the T0 reference, by a
    transfer weight ``alpha in [0,1]`` decided PER ROW from gate signals that are all available at TEST
    time without any label:
        gate = (domain_overlap_score >= overlap_min)
               AND (per-row stable-feature coverage >= coverage_min)
               AND (fold club-training support >= support_min)
               AND (row availability != 'unavailable')
    When the gate fails, ``alpha = 0`` and the model returns exactly T1 (or, if T1 itself is unfit /
    unavailable, the T0 reference). When the gate passes, ``alpha = alpha_max`` and the transfer model is
    used. ``alpha`` is fixed (not tuned on test) and the fold-level club support is an in-train quantity.
    This is the "falls back when coverage/overlap/support/quality inadequate" requirement, expressed as a
    deterministic, leakage-free gate.

  * ``T7CalibratedSimulation`` — takes the T6 remaining-goal intensities, converts them to P(final H/D/A)
    by Monte-Carlo simulation of remaining Poisson goals added to the current score, then applies an
    in-train monotone (isotonic-style, pooled-adjacent-violators) recalibration of the DRAW channel
    learned on TRAIN rows only. The calibration map is fit on (predicted P(draw), observed draw) pairs
    from the fold's TRAIN international rows and APPLIED to the held-out test rows. This is the only model
    in the ladder that may become a research candidate (judged vs T0).

Both expose ``predict_wdl(row) -> {H,D,A}``. T6 also exposes ``predict_intensity`` and ``gate_alpha``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import DOMAIN_CLUB, DOMAIN_INTERNATIONAL, T6_SELECTIVE_TRANSFER, T7_CALIBRATED_SIMULATION
from .domain_baselines import T0Reference, T1InternationalOnly
from .models import (
    cell_float,
    current_score_diff,
    remaining_goal_exact_wdl,
    remaining_goal_mc_wdl,
    stable_feature_columns,
)
from .partial_pooling import T5DomainWeighted, domain_weight


def _domain(r: dict) -> str:
    return r.get("domain") or DOMAIN_INTERNATIONAL


def _row_coverage(row: dict, cols: Sequence[str]) -> float:
    if not cols:
        return 0.0
    present = sum(1 for c in cols if cell_float(row, "feat_" + c) is not None)
    return present / len(cols)


# =================================================================================================
# T6 — selective transfer with alpha=0 fallback.
# =================================================================================================
@dataclass
class T6SelectiveTransfer:
    model_id: str = T6_SELECTIVE_TRANSFER
    short_id: str = "T6"
    alpha_max: float = 1.0
    overlap_min: float = 0.5
    coverage_min: float = 0.5
    support_min: int = 30            # min club-training MATCHES in the fold for transfer to be eligible
    always_on: bool = False          # ablation switch: T6-always-on-vs-selective
    cols: List[str] = field(default_factory=list)
    transfer: Optional[T5DomainWeighted] = None
    safe: Optional[T1InternationalOnly] = None
    reference: T0Reference = field(default_factory=T0Reference)
    fold_club_support_matches: int = 0
    transfer_eligible_fold: bool = False
    n_train_total: int = 0
    fitted: bool = False

    def fit(self, train_rows: Sequence[dict]) -> "T6SelectiveTransfer":
        pooled = list(train_rows)
        self.cols = stable_feature_columns(pooled)
        self.transfer = T5DomainWeighted(shared_ridge=1.0).fit(pooled)
        self.safe = T1InternationalOnly(ridge=1.0).fit(pooled)
        club_match_ids = {r.get("match_id") for r in pooled if _domain(r) == DOMAIN_CLUB}
        self.fold_club_support_matches = len(club_match_ids)
        self.transfer_eligible_fold = (self.fold_club_support_matches >= self.support_min)
        self.n_train_total = len(pooled)
        self.fitted = True
        return self

    def gate_alpha(self, row: dict) -> float:
        """Per-row transfer weight in [0, alpha_max]. 0 => pure fallback to the safe model. The gate uses
        only label-free, test-time-available signals + the in-train fold club support."""
        if self.always_on:
            return self.alpha_max
        if not self.transfer_eligible_fold:
            return 0.0
        overlap = cell_float(row, "domain_overlap_score")
        overlap = 0.0 if overlap is None else overlap
        cov = _row_coverage(row, self.cols)
        avail = (row.get("availability") or "").lower()
        gate_ok = (overlap >= self.overlap_min) and (cov >= self.coverage_min) and (avail != "unavailable")
        return self.alpha_max if gate_ok else 0.0

    def predict_intensity(self, row: dict) -> Dict[str, float]:
        if not self.fitted:
            return {"home": cell_float(row, "domain_baseline_home") or 0.0,
                    "away": cell_float(row, "domain_baseline_away") or 0.0}
        alpha = self.gate_alpha(row)
        if alpha <= 0.0:
            return self.safe.predict_intensity(row)
        tx = self.transfer.predict_intensity(row)
        sf = self.safe.predict_intensity(row)
        return {"home": alpha * tx["home"] + (1 - alpha) * sf["home"],
                "away": alpha * tx["away"] + (1 - alpha) * sf["away"]}

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        it = self.predict_intensity(row)
        return remaining_goal_exact_wdl(it["home"], it["away"], current_score_diff(row))


# =================================================================================================
# Monotone (PAV / isotonic) draw-channel recalibration, fit on TRAIN only.
# =================================================================================================
@dataclass
class _MonotoneCalibrator:
    """Pooled-adjacent-violators isotonic fit of observed-rate on predicted-prob, applied by interpolation.
    Deterministic; TRAIN only. Identity if too few points."""
    xs: List[float] = field(default_factory=list)   # sorted predicted probs (bin centers)
    ys: List[float] = field(default_factory=list)   # isotonic-fitted observed rates
    fitted: bool = False

    def fit(self, pairs: Sequence[Tuple[float, float]]) -> "_MonotoneCalibrator":
        pts = sorted((float(p), float(y)) for p, y in pairs if p is not None)
        if len(pts) < 10:
            self.fitted = False
            return self
        x = [p for p, _ in pts]
        y = [yy for _, yy in pts]
        w = [1.0] * len(y)
        # PAV
        i = 0
        ys = list(y)
        ws = list(w)
        xs = list(x)
        # standard pool-adjacent-violators on y, weights w
        blocks_y = []
        blocks_w = []
        blocks_x = []
        for j in range(len(ys)):
            cy, cw, cx = ys[j], ws[j], xs[j]
            blocks_y.append(cy); blocks_w.append(cw); blocks_x.append([cx])
            while len(blocks_y) > 1 and blocks_y[-2] > blocks_y[-1]:
                y2 = blocks_y.pop(); w2 = blocks_w.pop(); x2 = blocks_x.pop()
                y1 = blocks_y.pop(); w1 = blocks_w.pop(); x1 = blocks_x.pop()
                wm = w1 + w2
                blocks_y.append((y1 * w1 + y2 * w2) / wm)
                blocks_w.append(wm)
                blocks_x.append(x1 + x2)
        fx, fy = [], []
        for by, bx in zip(blocks_y, blocks_x):
            for xv in bx:
                fx.append(xv); fy.append(by)
        self.xs = fx
        self.ys = fy
        self.fitted = True
        return self

    def apply(self, p: float) -> float:
        if not self.fitted or not self.xs:
            return p
        if p <= self.xs[0]:
            return min(1.0, max(0.0, self.ys[0]))
        if p >= self.xs[-1]:
            return min(1.0, max(0.0, self.ys[-1]))
        lo, hi = 0, len(self.xs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.xs[mid] <= p:
                lo = mid
            else:
                hi = mid
        x0, x1 = self.xs[lo], self.xs[hi]
        y0, y1 = self.ys[lo], self.ys[hi]
        if x1 <= x0:
            return min(1.0, max(0.0, y0))
        t = (p - x0) / (x1 - x0)
        return min(1.0, max(0.0, y0 + t * (y1 - y0)))


# =================================================================================================
# T7 — calibrated Monte-Carlo W/D/L view of T6.
# =================================================================================================
@dataclass
class T7CalibratedSimulation:
    model_id: str = T7_CALIBRATED_SIMULATION
    short_id: str = "T7"
    n_sims: int = 4000
    use_mc: bool = True              # MC simulation; set False to use the exact Poisson-difference form
    calibrate_draw: bool = True
    base: Optional[T6SelectiveTransfer] = None
    draw_calibrator: _MonotoneCalibrator = field(default_factory=_MonotoneCalibrator)
    n_train_total: int = 0
    calibrator_fitted: bool = False
    fitted: bool = False

    def _raw_wdl(self, row: dict) -> Dict[str, float]:
        it = self.base.predict_intensity(row)
        sd = current_score_diff(row)
        if self.use_mc:
            # seed per-row deterministically from the match-id + minute so repeats are identical
            seed = (abs(hash((str(row.get("match_id")), str(row.get("snapshot_minute"))))) % (2 ** 31))
            return remaining_goal_mc_wdl(it["home"], it["away"], sd, n_sims=self.n_sims, seed=seed)
        return remaining_goal_exact_wdl(it["home"], it["away"], sd)

    def fit(self, train_rows: Sequence[dict]) -> "T7CalibratedSimulation":
        pooled = list(train_rows)
        self.base = T6SelectiveTransfer().fit(pooled)
        self.n_train_total = len(pooled)
        if self.calibrate_draw:
            intl_train = [r for r in pooled if _domain(r) == DOMAIN_INTERNATIONAL]
            pairs = []
            for r in intl_train:
                tgt = r.get("target_wdl")
                if tgt is None:
                    continue
                p = self._raw_wdl(r)
                pairs.append((p["D"], 1.0 if tgt == "D" else 0.0))
            self.draw_calibrator.fit(pairs)
            self.calibrator_fitted = self.draw_calibrator.fitted
        self.fitted = True
        return self

    def predict_wdl(self, row: dict) -> Dict[str, float]:
        if not self.fitted:
            return self.base.predict_wdl(row) if self.base else {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}
        raw = self._raw_wdl(row)
        if not (self.calibrate_draw and self.calibrator_fitted):
            return raw
        pd_new = self.draw_calibrator.apply(raw["D"])
        # redistribute the change across H/A proportionally so the simplex stays valid
        rest = raw["H"] + raw["A"]
        if rest <= 1e-12:
            return {"H": (1 - pd_new) / 2, "D": pd_new, "A": (1 - pd_new) / 2}
        scale = (1.0 - pd_new) / rest
        return {"H": raw["H"] * scale, "D": pd_new, "A": raw["A"] * scale}


__all__ = [
    "T6SelectiveTransfer", "T7CalibratedSimulation", "_MonotoneCalibrator",
]
