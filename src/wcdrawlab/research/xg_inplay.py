"""Leakage-safe LIVE in-play xG features from StatsBomb per-shot data.

For each in-play decision point at match minute `m`, the live xG state uses ONLY shots that occurred
STRICTLY BEFORE `m` (no look-ahead). This yields each team's accumulated xG "deserved goals", whose
difference vs the actual score ("xG surprise") is the orthogonal signal the score alone can't carry.

Data: StatsBomb Open Data (non-commercial research; "Data provided by StatsBomb").
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.ingest import canonical_team_name


def map_sb_matches(inplay_df: pd.DataFrame, shots_df: pd.DataFrame, tol_days: int = 1) -> dict:
    """our match_id -> StatsBomb sb_match_id, joined on canonical team pair + date (+/- tol_days)."""
    sb = shots_df.drop_duplicates("sb_match_id")[["sb_match_id", "home_team", "away_team", "match_date"]].copy()
    sb["pair"] = [frozenset((canonical_team_name(h), canonical_team_name(a)))
                  for h, a in zip(sb.home_team, sb.away_team)]
    sb["d"] = pd.to_datetime(sb.match_date, errors="coerce", utc=True)
    out = {}
    seen = inplay_df.drop_duplicates("match_id")
    for r in seen.itertuples():
        pair = frozenset((canonical_team_name(r.home_team), canonical_team_name(r.away_team)))
        target = pd.to_datetime(r.kickoff_utc, errors="coerce", utc=True)
        cand = sb[sb.pair == pair]
        if cand.empty:
            continue
        if pd.notna(target):
            cand = cand[cand.d.apply(lambda x: pd.notna(x) and abs((x - target).days) <= tol_days)]
        if not cand.empty:
            out[r.match_id] = cand.iloc[0].sb_match_id
    return out


def live_xg(match_shots: pd.DataFrame, home_team: str, decision_minute: float) -> tuple:
    """(xg_home, xg_away) accumulated from shots STRICTLY BEFORE decision_minute (leakage-safe)."""
    pre = match_shots[match_shots.minute < decision_minute]
    if pre.empty:
        return (0.0, 0.0)
    ch = canonical_team_name(home_team)
    is_home = pre.team.apply(lambda t: canonical_team_name(t) == ch)
    return (float(pre.loc[is_home, "xg"].sum()), float(pre.loc[~is_home, "xg"].sum()))


def attach_live_xg(inplay_df: pd.DataFrame, shots_df: pd.DataFrame) -> pd.DataFrame:
    """Add live_xg_home/away/diff + xg_surprise (xG_diff - score_diff) to in-play rows that map to a
    StatsBomb match. Rows without a mapped match get NaN (tracked by has_xg)."""
    m = map_sb_matches(inplay_df, shots_df)
    by_match = {mid: g.sort_values("minute") for mid, g in shots_df.groupby("sb_match_id")}
    df = inplay_df.copy()
    xh = np.full(len(df), np.nan); xa = np.full(len(df), np.nan)
    for i, r in enumerate(df.itertuples()):
        sbid = m.get(r.match_id)
        if sbid is None:
            continue
        h, a = live_xg(by_match[sbid], r.home_team, float(r.decision_minute))
        xh[i] = h; xa[i] = a
    df["live_xg_home"] = xh; df["live_xg_away"] = xa
    df["live_xg_diff"] = df.live_xg_home - df.live_xg_away
    df["xg_surprise"] = df.live_xg_diff - df.get("score_diff", df.live_xg_diff * 0)
    df["has_xg"] = df.live_xg_home.notna()
    return df
