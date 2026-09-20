"""Quality / leakage / honesty audits for the residual goal-intensity phase.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Pure checks (no fitting). They re-assert the invariants this phase depends on so a job can fail closed:

  * leakage_audit          -- no snapshot feature uses post-decision info; regulation only (period<=2,
                              minute<=90); no row carries a forbidden future-leak column.
  * no_target_in_features  -- the model column-set never contains a target/label key.
  * availability_audit     -- per-family availability coverage across rows (so a model never silently
                              consumes an everywhere-unavailable feature).
  * simplex_audit          -- a WDL prediction is a valid probability simplex.
  * no_2026_audit          -- no completed-2026-World-Cup row is present (delegates to event_process).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from wcdrawlab.research.event_process import eval as EPE
from . import availability as AV
from . import features as F

QUALITY_VERSION = "residual_intensity_quality_v1"
WDL = ("H", "D", "A")

# Keys that are TARGETS / labels and must never enter a model feature space.
TARGET_KEYS = {
    "target_wdl", "rem_goals_home", "rem_goals_away",
    "reg_home_goals", "reg_away_goals",
    "next_goal_side", "next_goal_minute", "next_goal_any_15",
    "any_goal_next5m", "any_goal_next10m", "any_goal_next15m",
    "home_scores_next5m", "home_scores_next10m", "home_scores_next15m",
    "away_scores_next5m", "away_scores_next10m", "away_scores_next15m",
    "sendoff_after",
}

# Columns that, if present in a snapshot feature row, would indicate a future / post-decision leak.
FORBIDDEN_FEATURE_COLS = {
    "final_score", "ft_home", "ft_away", "reg_home_goals", "reg_away_goals",
    "bridge_reg_home", "bridge_reg_away",
}


def no_target_in_features(feature_cols: Sequence[str]) -> Dict[str, object]:
    bad = sorted(set(feature_cols) & TARGET_KEYS)
    return {"ok": not bad, "leaked_targets": bad}


def leakage_audit(rows: Sequence[dict], feature_cols: Sequence[str]) -> Dict[str, object]:
    """Re-assert leakage invariants on the joined rows + the chosen feature column-set."""
    tgt = no_target_in_features(feature_cols)
    forbidden = sorted(set(feature_cols) & FORBIDDEN_FEATURE_COLS)
    # regulation-only structural check (period <= 2, snapshot_minute <= 90) where present
    period_ok = True
    minute_ok = True
    for r in rows:
        p = F.fnum(r, "period")
        if p is not None and p > 2:
            period_ok = False
        mn = F.fnum(r, "snapshot_minute")
        if mn is not None and mn > 90.0 + 1e-6:
            minute_ok = False
    return {
        "ok": bool(tgt["ok"] and not forbidden and period_ok and minute_ok),
        "no_target_in_features": tgt,
        "forbidden_feature_cols_present": forbidden,
        "regulation_period_ok": period_ok,
        "regulation_minute_ok": minute_ok,
    }


def availability_audit(rows: Sequence[dict]) -> Dict[str, object]:
    """Per-family + per-column availability coverage across rows; flags everywhere-unavailable columns."""
    fam_cov: Dict[str, float] = {}
    col_cov: Dict[str, float] = {}
    everywhere_unavailable: List[str] = []
    n = max(1, len(rows))
    for fam, cols in F.FEATURE_FAMILIES.items():
        cov = AV.coverage_report(rows, cols)
        col_cov.update(cov)
        fam_cov[fam] = round(sum(cov.values()) / max(1, len(cols)), 6)
    for c, frac in col_cov.items():
        if frac <= 0.0:
            everywhere_unavailable.append(c)
    return {
        "n_rows": len(rows),
        "family_coverage": fam_cov,
        "column_coverage": col_cov,
        "everywhere_unavailable_cols": sorted(everywhere_unavailable),
    }


def simplex_audit(p: Dict[str, float], tol: float = 1e-6) -> bool:
    if set(p.keys()) != set(WDL):
        return False
    for k in WDL:
        v = p[k]
        if v < -1e-9 or v > 1.0 + 1e-9:
            return False
    return abs(sum(p.values()) - 1.0) <= tol


def no_2026_audit(rows: Sequence[dict]) -> Dict[str, object]:
    try:
        EPE.assert_no_2026(rows)
        return {"ok": True}
    except AssertionError as e:
        return {"ok": False, "reason": str(e)}
