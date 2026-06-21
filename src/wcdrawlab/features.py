from __future__ import annotations

import numpy as np
import pandas as pd


def add_basic_outcome_columns(df: pd.DataFrame, goals_a="goals_a", goals_b="goals_b") -> pd.DataFrame:
    out = df.copy()
    out["outcome"] = np.select(
        [out[goals_a] > out[goals_b], out[goals_a] == out[goals_b], out[goals_a] < out[goals_b]],
        ["A", "D", "B"],
        default=None,
    )
    out["is_draw"] = (out["outcome"] == "D").astype(int)
    return out


def add_strength_deltas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    pairs = [
        ("elo_a", "elo_b", "elo_delta"),
        ("fifa_points_z_a", "fifa_points_z_b", "fifa_z_delta"),
        ("fifa_rank_percentile_a", "fifa_rank_percentile_b", "fifa_rank_pct_delta"),
        ("market_ability_a", "market_ability_b", "market_ability_delta"),
        ("squad_value_log_a", "squad_value_log_b", "squad_value_log_delta"),
    ]
    for a, b, name in pairs:
        if a in out.columns and b in out.columns:
            out[name] = out[a] - out[b]
            out[f"abs_{name}"] = out[name].abs()
    return out


def build_pre_match_group_state(matches: pd.DataFrame) -> pd.DataFrame:
    """Compute points/GD/goals/draws before each group-stage match.

    Assumes rows are chronological and completed matches have goals.
    """
    required = {"match_id", "kickoff_utc", "group", "team_a", "team_b", "goals_a", "goals_b"}
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"matches missing columns: {missing}")

    rows = []
    state: dict[str, dict[str, dict[str, float]]] = {}
    group_draws: dict[str, int] = {}
    group_goals: dict[str, int] = {}
    group_played: dict[str, int] = {}

    for _, r in matches.sort_values("kickoff_utc").iterrows():
        g = r["group"]
        if pd.isna(g):
            continue
        if g not in state:
            state[g] = {}
            group_draws[g] = 0
            group_goals[g] = 0
            group_played[g] = 0
        for t in [r["team_a"], r["team_b"]]:
            state[g].setdefault(t, {"points": 0, "gd": 0, "gf": 0, "ga": 0, "played": 0})
        a, b = r["team_a"], r["team_b"]
        sa, sb = state[g][a], state[g][b]
        rows.append({
            "match_id": r["match_id"],
            "points_a_pre": sa["points"],
            "points_b_pre": sb["points"],
            "gd_a_pre": sa["gd"],
            "gd_b_pre": sb["gd"],
            "gf_a_pre": sa["gf"],
            "gf_b_pre": sb["gf"],
            "played_a_pre": sa["played"],
            "played_b_pre": sb["played"],
            "prior_group_draws": group_draws[g],
            "prior_group_goals": group_goals[g],
            "prior_group_matches": group_played[g],
            "prior_group_goals_per_match": group_goals[g] / group_played[g] if group_played[g] else 0.0,
        })

        if pd.notna(r["goals_a"]) and pd.notna(r["goals_b"]):
            ga, gb = int(r["goals_a"]), int(r["goals_b"])
            if ga > gb:
                pa, pb = 3, 0
            elif ga == gb:
                pa, pb = 1, 1
                group_draws[g] += 1
            else:
                pa, pb = 0, 3
            sa["points"] += pa; sb["points"] += pb
            sa["gd"] += ga - gb; sb["gd"] += gb - ga
            sa["gf"] += ga; sb["gf"] += gb
            sa["ga"] += gb; sb["ga"] += ga
            sa["played"] += 1; sb["played"] += 1
            group_goals[g] += ga + gb
            group_played[g] += 1

    state_df = pd.DataFrame(rows)
    return matches.merge(state_df, on="match_id", how="left")


def add_schedule_adjusted_state(df: pd.DataFrame) -> pd.DataFrame:
    """Add simple schedule-adjusted points features if opponent strength is present.

    Expected points so far is approximated from pre-match Elo difference if available.
    For real deployment, compute expected points against actual opponents already played.
    """
    out = df.copy()
    if {"points_a_pre", "points_b_pre", "played_a_pre", "played_b_pre"}.issubset(out.columns):
        out["points_per_game_a_pre"] = out["points_a_pre"] / out["played_a_pre"].replace(0, np.nan)
        out["points_per_game_b_pre"] = out["points_b_pre"] / out["played_b_pre"].replace(0, np.nan)
        out[["points_per_game_a_pre", "points_per_game_b_pre"]] = out[["points_per_game_a_pre", "points_per_game_b_pre"]].fillna(0)
        out["group_state_points_delta"] = out["points_a_pre"] - out["points_b_pre"]
        out["group_state_gd_delta"] = out["gd_a_pre"] - out["gd_b_pre"]
    return out


def add_low_block_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Proxy for underdog defensive low-block draw inflation.

    Higher when there is a favorite/underdog gap, low market total, and underdog can benefit from a draw.
    """
    out = df.copy()
    total = out.get("market_total_goals", pd.Series(2.5, index=out.index))
    abs_elo = out.get("abs_elo_delta", pd.Series(0.0, index=out.index))
    draw_util = out.get("mutual_draw_utility", pd.Series(0.0, index=out.index))
    low_total = np.clip((2.7 - total) / 1.2, 0, 1)
    mismatch = np.clip(abs_elo / 450.0, 0, 1)
    out["low_block_risk"] = low_total * mismatch * (0.5 + 0.5 * np.clip(draw_util, 0, 1))
    return out


def add_travel_fatigue(df: pd.DataFrame) -> pd.DataFrame:
    """Simple travel/fatigue feature from rest/travel/timezone/heat columns if present."""
    out = df.copy()
    rest_a = out.get("rest_days_a", pd.Series(4.0, index=out.index))
    rest_b = out.get("rest_days_b", pd.Series(4.0, index=out.index))
    miles_a = out.get("travel_miles_last7_a", pd.Series(0.0, index=out.index))
    miles_b = out.get("travel_miles_last7_b", pd.Series(0.0, index=out.index))
    tz_a = out.get("timezone_shift_a", pd.Series(0.0, index=out.index)).abs()
    tz_b = out.get("timezone_shift_b", pd.Series(0.0, index=out.index)).abs()
    heat = out.get("heat_index", pd.Series(75.0, index=out.index))
    fatigue_a = np.clip((4 - rest_a) / 3, 0, 1) + np.clip(miles_a / 3000, 0, 1) + np.clip(tz_a / 4, 0, 1) + np.clip((heat - 80) / 25, 0, 1)
    fatigue_b = np.clip((4 - rest_b) / 3, 0, 1) + np.clip(miles_b / 3000, 0, 1) + np.clip(tz_b / 4, 0, 1) + np.clip((heat - 80) / 25, 0, 1)
    out["travel_fatigue_a"] = fatigue_a
    out["travel_fatigue_b"] = fatigue_b
    out["travel_fatigue"] = (fatigue_a + fatigue_b) / 4.0
    out["travel_fatigue_delta"] = fatigue_a - fatigue_b
    return out
