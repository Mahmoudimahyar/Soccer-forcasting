"""Monte-Carlo remaining-score SIMULATION from home/away intensities -> P(final H / D / A).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Given side-specific expected REMAINING regulation goals (lam_h, lam_a) at the decision minute and the
CURRENT regulation score difference, this module produces P(final H / D / A) by simulating remaining
goals as independent Poisson draws and combining with the current diff. It also exposes the exact
analytic convolution (reused from event_process.models.wdl_from_intensities) so a model can choose the
closed form when it wants a deterministic, draw-free answer.

The simulator:
  * is seeded and deterministic (numpy default_rng(seed)); identical inputs -> identical output.
  * returns a valid probability simplex over {H, D, A} (non-negative, sums to 1).
  * uses ONLY (lam_h, lam_a, current_diff) -- no target, no future event.

This is the engine behind research.residual.calibrated_simulation_r5 (simulate, then calibrate in-train).
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from wcdrawlab.research.event_process import models as EPM  # exact analytic convolution + reference

SIMULATION_VERSION = "residual_intensity_simulation_v1"
WDL = ["H", "D", "A"]


def _norm(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, v) for v in d.values())
    if s <= 0:
        return {k: 1.0 / len(WDL) for k in WDL}
    return {k: max(0.0, d.get(k, 0.0)) / s for k in WDL}


def analytic_wdl(lam_h: float, lam_a: float, current_diff: int, kmax: int = 10) -> Dict[str, float]:
    """Exact independent-Poisson remaining-goal convolution combined with the current diff. Reuses the
    locked event_process implementation so this phase's analytic path is identical to W2's."""
    return EPM.wdl_from_intensities(lam_h, lam_a, current_diff, kmax=kmax)


def simulate_wdl(lam_h: float, lam_a: float, current_diff: int,
                 n_sims: int = 4000, seed: int = 12345) -> Dict[str, float]:
    """Monte-Carlo P(final H / D / A): draw remaining home/away goals ~ Poisson(lam), add the current
    diff, tally outcomes. Deterministic for fixed seed. Returns a valid simplex over {H, D, A}."""
    lam_h = max(0.0, float(lam_h))
    lam_a = max(0.0, float(lam_a))
    rng = np.random.default_rng(int(seed))
    gh = rng.poisson(lam_h, size=int(n_sims))
    ga = rng.poisson(lam_a, size=int(n_sims))
    final_diff = int(current_diff) + (gh - ga)
    pH = float(np.mean(final_diff > 0))
    pD = float(np.mean(final_diff == 0))
    pA = float(np.mean(final_diff < 0))
    return _norm({"H": pH, "D": pD, "A": pA})


def wdl_from_intensities(lam_h: float, lam_a: float, current_diff: int,
                         method: str = "analytic", n_sims: int = 4000,
                         seed: int = 12345) -> Dict[str, float]:
    """Dispatch: 'analytic' (exact convolution, default -- deterministic, fast) or 'mc' (Monte-Carlo)."""
    if method == "mc":
        return simulate_wdl(lam_h, lam_a, current_diff, n_sims=n_sims, seed=seed)
    return analytic_wdl(lam_h, lam_a, current_diff)


def is_simplex(p: Dict[str, float], tol: float = 1e-9) -> bool:
    """True iff p is a valid probability simplex over {H, D, A}."""
    if set(p.keys()) != set(WDL):
        return False
    for k in WDL:
        v = p[k]
        if not np.isfinite(v) or v < -tol or v > 1.0 + tol:
            return False
    return abs(sum(p.values()) - 1.0) <= 1e-6
