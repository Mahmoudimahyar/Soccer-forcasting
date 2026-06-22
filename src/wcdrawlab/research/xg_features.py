"""PRE-REGISTERED in-play xG feature families (Phase 5). Exactly six families, fixed before testing:
  1. xg_diff_before        - cumulative home-away xG, shots strictly before decision minute
  2. roll5_xg_diff         - home-away xG over [m-5, m)
  3. roll10_xg_diff        - home-away xG over [m-10, m)
  4. shotcount5_diff / shotcount10_diff - home-away shot counts over last 5 / 10 minutes
  5. tsl_shot              - minutes since last shot by either team (capped at decision minute)
  6. tsl_major             - minutes since last 'major chance' (xg >= 0.2)
All use only shots with minute < decision minute (leakage-safe). No other variants are tested.

FAMILIES maps a family key -> the feature column(s) it contributes (for bounded model selection).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.ingest import canonical_team_name

FAMILIES = {
    "f1_xg_before": ["xg_diff_before"],
    "f2_roll5": ["roll5_xg_diff"],
    "f3_roll10": ["roll10_xg_diff"],
    "f4_shotcount": ["shotcount5_diff", "shotcount10_diff"],
    "f5_tsl_shot": ["tsl_shot"],
    "f6_tsl_major": ["tsl_major"],
}
ALL_XG_COLS = [c for cols in FAMILIES.values() for c in cols]
MAJOR = 0.2


def families_for_match(match_shots: pd.DataFrame, home: str, away: str, minute: float) -> dict:
    pre = match_shots[match_shots["minute"] < minute]
    ch = canonical_team_name(home)

    def diff(sub):
        """(home_xg, away_xg, home_n, away_n) for a shot subset."""
        if len(sub) == 0:
            return 0.0, 0.0, 0, 0
        ish = sub["team"].map(lambda t: canonical_team_name(t) == ch).to_numpy()
        xg = sub["xg"].to_numpy(dtype=float)
        return float(xg[ish].sum()), float(xg[~ish].sum()), int(ish.sum()), int((~ish).sum())

    hxg, axg, _, _ = diff(pre)
    h5x, a5x, h5n, a5n = diff(pre[pre["minute"] >= minute - 5])
    h10x, a10x, h10n, a10n = diff(pre[pre["minute"] >= minute - 10])
    last_shot = pre["minute"].max() if len(pre) else np.nan
    maj = pre[pre["xg"] >= MAJOR]
    last_major = maj["minute"].max() if len(maj) else np.nan
    return {
        "xg_diff_before": hxg - axg,
        "roll5_xg_diff": h5x - a5x,
        "roll10_xg_diff": h10x - a10x,
        "shotcount5_diff": float(h5n - a5n),
        "shotcount10_diff": float(h10n - a10n),
        "tsl_shot": float(minute - last_shot) if last_shot == last_shot else float(minute),
        "tsl_major": float(minute - last_major) if last_major == last_major else float(minute),
    }


def attach_xg_families(state_df: pd.DataFrame, shots_df: pd.DataFrame) -> pd.DataFrame:
    """Add the six pre-registered xG family columns to state rows (keyed by sb_match_id+decision_minute)."""
    by_match = {mid: g for mid, g in shots_df.groupby("sb_match_id")}
    cols = {c: np.full(len(state_df), np.nan) for c in ALL_XG_COLS}
    for i, r in enumerate(state_df.itertuples()):
        ms = by_match.get(r.sb_match_id)
        if ms is None:
            continue
        f = families_for_match(ms, r.home_team, r.away_team, float(r.decision_minute))
        for c in ALL_XG_COLS:
            cols[c][i] = f[c]
    out = state_df.copy()
    for c in ALL_XG_COLS:
        out[c] = cols[c]
    return out
