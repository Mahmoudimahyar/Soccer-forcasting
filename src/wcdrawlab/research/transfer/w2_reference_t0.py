"""``research.transfer.w2_reference_t0`` -- the parameter-free remaining-time Poisson REFERENCE.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This is the single REFERENCE T0 against which every transfer candidate (T1..T7) is judged. It is the
SAME parameter-free remaining-time Poisson reference used by the locked event-process e2 family and the
residual-intensity phase (``dynamic_models.R2_BASE`` = 1.35 goals per team per 90', scaled by remaining
regulation fraction). It is NOT a fitted model, NOT the frozen runtime M2, and it never touches a target:
it is a closed form of (current score diff, remaining minutes) only.

Two reference views are exposed:
  * ``reference_intensity(row)``  -- expected REMAINING regulation goals for home/away (the residual
    baseline every transfer model is expressed RELATIVE to);
  * ``reference_wdl(row)``        -- P(final H/D/A) from the same closed form (for the W/D/L angle).

Both are pure, deterministic, and leakage-free. The intensity is symmetric across home/away (the T0
reference deliberately carries NO domain knowledge -- that is exactly what the transfer ladder must beat).
"""
from __future__ import annotations

from typing import Dict, Optional

from wcdrawlab.research import dynamic_models as DM

# Parameter-free reference rate (goals per team per 90'). Identical to the e2 / W2 reference and
# DM.R2_BASE. NOT the frozen runtime M2.
BASE_RATE_PER90 = DM.R2_BASE  # 1.35
MODEL_ID = "research.transfer.w2_reference_t0"
REFERENCE_VERSION = "w2_reference_t0_v1"


def _fnum(row: dict, col: str) -> Optional[float]:
    """Float value of a cell, or None if absent / blank / unparseable. Never coerces a missing cell to
    0 (missingness is preserved upstream and by the dataset builder)."""
    if col not in row:
        return None
    v = row.get(col)
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


def remaining_fraction(row: dict) -> float:
    """Fraction of regulation still to play in [0, 1]. Prefers the explicit remaining-minutes column;
    falls back to (90 - snapshot_minute)/90. Clamped to [0, 1]."""
    rem = _fnum(row, "remaining_regulation_min")
    if rem is None:
        mn = _fnum(row, "snapshot_minute")
        rem = (90.0 - mn) if mn is not None else 90.0
    return max(0.0, min(1.0, rem / 90.0))


def current_score_diff(row: dict) -> int:
    """Current regulation (home - away) goal difference at the decision minute."""
    gd = _fnum(row, "goals_diff")
    if gd is not None:
        return int(round(gd))
    gh = _fnum(row, "goals_home")
    ga = _fnum(row, "goals_away")
    if gh is not None and ga is not None:
        return int(round(gh - ga))
    return 0


def reference_intensity(row: dict) -> Dict[str, float]:
    """Expected REMAINING regulation goals for home / away under the parameter-free T0 reference. Both
    teams share the base rate scaled by remaining time (symmetric); the diff is identically 0. This is
    the residual BASELINE the transfer ladder must improve on."""
    lam = BASE_RATE_PER90 * remaining_fraction(row)
    return {
        "t0_lam_home": lam,
        "t0_lam_away": lam,
        "t0_lam_diff": 0.0,
        "t0_lam_total": 2.0 * lam,
        "t0_base_rate_per90": BASE_RATE_PER90,
        "t0_remaining_fraction": remaining_fraction(row),
    }


def reference_wdl(row: dict) -> Dict[str, float]:
    """P(final H/D/A) from the same parameter-free remaining-time Poisson closed form (current score
    diff + remaining minutes). Reuses dynamic_models.r2_remaining_time_poisson so this is byte-identical
    to the locked W2 reference. Pure / leakage-free."""
    rem_min = _fnum(row, "remaining_regulation_min")
    if rem_min is None:
        mn = _fnum(row, "snapshot_minute")
        rem_min = (90.0 - mn) if mn is not None else 90.0
    rem_min = max(0.0, min(90.0, rem_min))
    p = DM.r2_remaining_time_poisson({"remaining": rem_min, "score_diff": current_score_diff(row)})
    return {"t0_prob_H": p["H"], "t0_prob_D": p["D"], "t0_prob_A": p["A"]}


def annotate(rows) -> None:
    """Attach the T0 reference intensity + W/D/L probs to each row in-place (idempotent). Never
    overwrites a target; only adds t0_* columns."""
    for r in rows:
        r.update(reference_intensity(r))
        r.update(reference_wdl(r))
