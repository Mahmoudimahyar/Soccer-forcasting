"""Residual goal-intensity FEATURE families.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Six interpretable feature families over the already-leakage-truncated event-process snapshot columns
(built by scripts/build_event_process_snapshots.py; every column at minute t uses only events with
match-clock minute <= t). Nothing here recomputes from raw events; nothing here touches a target.

The families (spec verbatim):
  1. reference_state     -- W2 remaining-time reference intensities (home/away/diff) + score/clock state
  2. recent_chance       -- recent chance quality: rolling xG / shots windows + time-since-chance
  3. possession_territory-- possession share, field tilt, final-third actions, box entries, territory
  4. transition          -- transition / disruption: recoveries, turnovers, momentum/acceleration
  5. set_pieces          -- corners, attacking free kicks, set-piece pressure differentials
  6. quality_availability-- discipline (cards/sendoffs/player counts), subs, xg_present, n_events

Every model in this phase composes a SUBSET of these column lists. Missingness is preserved upstream
(string CSV cells may be empty); the availability gate (availability.py) + DM.FeatureSpace decide how an
absent cell is handled (TRAIN-mean impute + ``__unknown`` indicator) -- features.py NEVER zero-fills.

The W2 reference intensities (family 1) are the residual baseline: r0 / i0 are computed directly from
them; every residual/correction model is expressed RELATIVE to these. They are computed here with the
exact same parameter-free rule as the event_process e2 reference (DM.R2_BASE per team per 90', scaled by
remaining regulation fraction), so this phase's reference is identical to the locked W2.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from wcdrawlab.research import dynamic_models as DM

# Parameter-free W2 reference rate (goals per team per 90'). Identical to the event_process e2 reference
# and DM.R2_BASE; this is NOT the frozen runtime M2.
W2_BASE_RATE_PER90 = DM.R2_BASE  # 1.35
FEATURES_VERSION = "residual_intensity_features_v1"


# =================================================================================================
# typed cell access (preserve missingness; never coerce a missing cell to 0)
# =================================================================================================
def fnum(row: dict, col: str) -> Optional[float]:
    """Float value of a snapshot cell, or None if absent / blank / unparseable. NEVER returns 0 for a
    missing cell -- missingness is preserved so the availability gate + FeatureSpace can handle it."""
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


def _remaining_fraction(row: dict) -> float:
    """Fraction of regulation still to play in [0, 1]. Prefers the explicit remaining-minutes column;
    falls back to (90 - snapshot_minute)/90. Clamped to [0, 1]."""
    rem = fnum(row, "remaining_regulation_min")
    if rem is None:
        mn = fnum(row, "snapshot_minute")
        rem = (90.0 - mn) if mn is not None else 90.0
    return max(0.0, min(1.0, rem / 90.0))


def _current_diff(row: dict) -> int:
    """Current regulation (home - away) goal difference at the decision minute."""
    gd = fnum(row, "goals_diff")
    if gd is not None:
        return int(round(gd))
    gh = fnum(row, "goals_home")
    ga = fnum(row, "goals_away")
    if gh is not None and ga is not None:
        return int(round(gh - ga))
    return 0


# =================================================================================================
# Family 1: reference state -- the W2 home/away reference intensities + score/clock state
# =================================================================================================
def w2_reference_intensities(row: dict) -> Dict[str, float]:
    """W2 (parameter-free) expected REMAINING regulation goals for home / away. Both teams share the
    league base rate scaled by remaining time -- the residual baseline every model is relative to."""
    lam = W2_BASE_RATE_PER90 * _remaining_fraction(row)
    return {"w2_lam_home": lam, "w2_lam_away": lam, "w2_lam_diff": 0.0, "w2_lam_total": 2.0 * lam}


# annotation: attach the reference intensities + remaining fraction to a row in-place (used by
# simulation / intensity families). Never overwrites a target; only adds w2_* columns.
def annotate_w2(rows: Sequence[dict]) -> None:
    for r in rows:
        ref = w2_reference_intensities(r)
        r.update(ref)
        r["w2_remaining_fraction"] = _remaining_fraction(r)
        r["w2_current_diff"] = _current_diff(r)


# Reference-state COLUMNS usable as model features (the W2 anchors are injected by DM.FeatureSpace's
# r2 anchor separately; these are the raw causal state columns).
REFERENCE_STATE_COLS: List[str] = [
    "goals_diff", "remaining_regulation_min", "snapshot_minute", "period",
    "players_diff",
]

# =================================================================================================
# Family 2: recent chance quality (rolling xG / shot windows + time-since-chance)
# =================================================================================================
RECENT_CHANCE_COLS: List[str] = [
    "cum_xg_home", "cum_xg_away", "cum_xg_diff", "cum_xg_total",
    "xg_last1m_diff", "xg_last2m_diff", "xg_last5m_diff", "xg_last10m_diff", "xg_last15m_diff",
    "xg_current_half_diff", "xg_momentum_diff_10m", "xg_acceleration_diff",
    "shots_diff", "shots_on_target_diff",
    "shots_last5m_home", "shots_last5m_away", "shots_last10m_home", "shots_last10m_away",
    "min_since_last_shot_any", "min_since_last_shot_home", "min_since_last_shot_away",
    "min_since_major_chance",
]

# =================================================================================================
# Family 3: possession + territory
# =================================================================================================
POSSESSION_TERRITORY_COLS: List[str] = [
    "poss_share_home", "poss_share_diff",
    "final_third_actions_diff", "field_tilt_home",
    "box_entries_home", "box_entries_away", "box_entries_diff",
]

# =================================================================================================
# Family 4: transition / disruption
# =================================================================================================
TRANSITION_COLS: List[str] = [
    "recoveries_diff", "turnovers_diff",
    "recoveries_home", "recoveries_away", "turnovers_home", "turnovers_away",
]

# =================================================================================================
# Family 5: set pieces
# =================================================================================================
SET_PIECE_COLS: List[str] = [
    "corners_home", "corners_away", "corners_diff",
    "att_free_kicks_home", "att_free_kicks_away", "att_free_kicks_diff",
]

# =================================================================================================
# Family 6: quality / availability (discipline, subs, source-coverage signals)
# =================================================================================================
QUALITY_AVAILABILITY_COLS: List[str] = [
    "yellow_diff", "sendoff_diff", "subs_used_diff",
    "yellow_home", "yellow_away", "sendoff_home", "sendoff_away",
    "n_events_observed",
]

# Family registry (name -> column list). The availability gate audits each list against actual rows.
FEATURE_FAMILIES: Dict[str, List[str]] = {
    "reference_state": REFERENCE_STATE_COLS,
    "recent_chance": RECENT_CHANCE_COLS,
    "possession_territory": POSSESSION_TERRITORY_COLS,
    "transition": TRANSITION_COLS,
    "set_pieces": SET_PIECE_COLS,
    "quality_availability": QUALITY_AVAILABILITY_COLS,
}

# All feature columns across families (deduplicated, stable order). The W2 reference intensity columns
# (w2_*) are NOT in this list -- they are injected via the FeatureSpace anchor / simulation directly.
ALL_FEATURE_COLS: List[str] = []
for _fam in ("reference_state", "recent_chance", "possession_territory",
             "transition", "set_pieces", "quality_availability"):
    for _c in FEATURE_FAMILIES[_fam]:
        if _c not in ALL_FEATURE_COLS:
            ALL_FEATURE_COLS.append(_c)


def family_of(col: str) -> Optional[str]:
    for fam, cols in FEATURE_FAMILIES.items():
        if col in cols:
            return fam
    return None


def columns_for(families: Sequence[str]) -> List[str]:
    """Ordered, deduplicated column list for a set of families (used to build a model column-set)."""
    out: List[str] = []
    for fam in families:
        for c in FEATURE_FAMILIES.get(fam, []):
            if c not in out:
                out.append(c)
    return out
