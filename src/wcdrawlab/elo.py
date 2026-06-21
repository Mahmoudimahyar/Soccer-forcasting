from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re

import numpy as np
import pandas as pd

from wcdrawlab.ratings import elo_expected_score


@dataclass(frozen=True)
class EloUpdateConfig:
    """Configuration for immediate post-match Elo updates.

    Defaults implement a World-Football-Elo-like zero-sum update for national-team
    football. The values are intentionally configurable because FIFA SUM, World
    Football Elo, and private/internal Elo systems do not use exactly the same
    weights.
    """

    k: float = 60.0
    scale: float = 400.0
    home_advantage: float = 0.0
    round_change: bool = True
    default_initial_elo: float = 1500.0
    source: str = "internal_elo_after_match"


def goal_difference_multiplier(goal_diff: int) -> float:
    """World-Football-Elo-style goal-difference multiplier.

    Draws and one-goal wins use 1.0; two-goal wins use 1.5; wins by three or
    more use (11 + N) / 8, where N is absolute goal difference.
    """

    n = abs(int(goal_diff))
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.5
    return (11.0 + n) / 8.0


def match_result_score(goals_for: int, goals_against: int) -> float:
    """Return Elo score S: win=1, draw=0.5, loss=0."""

    if goals_for > goals_against:
        return 1.0
    if goals_for == goals_against:
        return 0.5
    return 0.0


def _latest_rating_row(ratings: pd.DataFrame, team: str, as_of: pd.Timestamp | None = None) -> pd.Series | None:
    if ratings.empty or "team" not in ratings.columns or "elo" not in ratings.columns:
        return None
    df = ratings.copy()
    if "rating_date" in df.columns:
        df["rating_date"] = pd.to_datetime(df["rating_date"], utc=True, errors="coerce")
        if as_of is not None:
            as_of = pd.to_datetime(as_of, utc=True)
            df = df[(df["rating_date"].isna()) | (df["rating_date"] <= as_of)]
    team_df = df[df["team"].astype(str) == str(team)].copy()
    if team_df.empty:
        return None
    if "rating_date" in team_df.columns:
        team_df = team_df.sort_values("rating_date")
    return team_df.iloc[-1]


def latest_elo(ratings: pd.DataFrame, team: str, as_of: pd.Timestamp | None = None, default: float = 1500.0) -> float:
    """Latest known Elo for a team before `as_of`, with a safe default."""

    row = _latest_rating_row(ratings, team, as_of=as_of)
    if row is None or pd.isna(row.get("elo")):
        return float(default)
    return float(row["elo"])


def compute_post_match_elo(
    elo_a: float,
    elo_b: float,
    goals_a: int,
    goals_b: int,
    config: EloUpdateConfig | None = None,
) -> dict[str, float]:
    """Compute a zero-sum Elo update from one final score.

    Team A's expected score is computed from (elo_a + home_advantage - elo_b).
    The same points change is subtracted from team B, preserving the rating pool.
    """

    cfg = config or EloUpdateConfig()
    if goals_a < 0 or goals_b < 0:
        raise ValueError("Goals must be non-negative integers.")
    s_a = match_result_score(goals_a, goals_b)
    expected_a = float(elo_expected_score((float(elo_a) + cfg.home_advantage) - float(elo_b), scale=cfg.scale))
    g = goal_difference_multiplier(int(goals_a) - int(goals_b))
    raw_change = cfg.k * g * (s_a - expected_a)
    change = float(round(raw_change)) if cfg.round_change else float(raw_change)
    new_a = float(elo_a) + change
    new_b = float(elo_b) - change
    return {
        "elo_a_pre": float(elo_a),
        "elo_b_pre": float(elo_b),
        "expected_a": expected_a,
        "expected_b": 1.0 - expected_a,
        "score_a": s_a,
        "score_b": 1.0 - s_a,
        "goal_multiplier": g,
        "elo_change_a": change,
        "elo_change_b": -change,
        "elo_a_post": new_a,
        "elo_b_post": new_b,
    }


def _safe_timestamp_after_match(match_row: pd.Series, completed_at: str | None = None) -> pd.Timestamp:
    if completed_at:
        return pd.to_datetime(completed_at, utc=True)
    if "kickoff_utc" in match_row and pd.notna(match_row["kickoff_utc"]):
        # Use kickoff + 2 hours as a deterministic final-whistle proxy. This is
        # earlier than later same-day fixtures and avoids using the current wall
        # clock during historical replays.
        return pd.to_datetime(match_row["kickoff_utc"], utc=True) + pd.Timedelta(hours=2)
    return pd.Timestamp.utcnow()


def append_post_match_elo_rows(
    ratings: pd.DataFrame,
    match_row: pd.Series,
    goals_a: int,
    goals_b: int,
    completed_at: str | None = None,
    config: EloUpdateConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append post-match Elo rows for both teams and return (ratings, audit_row)."""

    cfg = config or EloUpdateConfig()
    out = ratings.copy() if ratings is not None else pd.DataFrame(columns=["team", "rating_date", "elo", "source", "notes"])
    if "rating_date" in out.columns:
        out["rating_date"] = pd.to_datetime(out["rating_date"], utc=True, errors="coerce")
    else:
        out["rating_date"] = pd.NaT
    for col in ["team", "elo", "source", "notes"]:
        if col not in out.columns:
            out[col] = np.nan

    team_a = str(match_row["team_a"])
    team_b = str(match_row["team_b"])
    as_of = pd.to_datetime(match_row.get("kickoff_utc"), utc=True) if "kickoff_utc" in match_row else None
    elo_a = latest_elo(out, team_a, as_of=as_of, default=cfg.default_initial_elo)
    elo_b = latest_elo(out, team_b, as_of=as_of, default=cfg.default_initial_elo)
    update = compute_post_match_elo(elo_a, elo_b, goals_a, goals_b, cfg)
    rating_date = _safe_timestamp_after_match(match_row, completed_at=completed_at)
    match_id = str(match_row.get("match_id", "unknown_match"))
    note = (
        f"post-match Elo for {match_id}; score {goals_a}-{goals_b}; "
        f"K={cfg.k}; G={update['goal_multiplier']:.3f}; expected_a={update['expected_a']:.3f}"
    )
    new_rows = pd.DataFrame([
        {"team": team_a, "rating_date": rating_date, "elo": update["elo_a_post"], "source": cfg.source, "notes": note},
        {"team": team_b, "rating_date": rating_date, "elo": update["elo_b_post"], "source": cfg.source, "notes": note},
    ])
    out = pd.concat([out, new_rows], ignore_index=True)
    audit = pd.DataFrame([{**{
        "match_id": match_id,
        "rating_date": rating_date,
        "team_a": team_a,
        "team_b": team_b,
        "goals_a": int(goals_a),
        "goals_b": int(goals_b),
        "k": cfg.k,
        "scale": cfg.scale,
        "home_advantage": cfg.home_advantage,
        "round_change": cfg.round_change,
        "source": cfg.source,
    }, **update}])
    return out, audit


def update_elo_after_match_table(
    ratings: pd.DataFrame,
    matches: pd.DataFrame,
    match_id: str,
    goals_a: int,
    goals_b: int,
    completed_at: str | None = None,
    config: EloUpdateConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Find match_id in a match table and append post-match Elo rows."""

    idx = matches.index[matches["match_id"].astype(str) == str(match_id)]
    if len(idx) != 1:
        raise ValueError(f"match_id {match_id!r} not found uniquely; matched {len(idx)} rows.")
    return append_post_match_elo_rows(ratings, matches.loc[idx[0]], goals_a, goals_b, completed_at=completed_at, config=config)


def write_elo_outputs(
    ratings: pd.DataFrame,
    audit: pd.DataFrame,
    elo_path: str | Path,
    audit_path: str | Path,
) -> tuple[Path, Path]:
    """Persist current Elo table and append the audit row."""

    elo_p = Path(elo_path)
    audit_p = Path(audit_path)
    elo_p.parent.mkdir(parents=True, exist_ok=True)
    audit_p.parent.mkdir(parents=True, exist_ok=True)
    ratings_out = ratings.copy()
    if "rating_date" in ratings_out.columns:
        ratings_out["rating_date"] = pd.to_datetime(ratings_out["rating_date"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    ratings_out.to_csv(elo_p, index=False)

    audit_out = audit.copy()
    if audit_p.exists():
        old = pd.read_csv(audit_p)
        audit_out = pd.concat([old, audit_out], ignore_index=True)
    if "rating_date" in audit_out.columns:
        audit_out["rating_date"] = pd.to_datetime(audit_out["rating_date"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    audit_out.to_csv(audit_p, index=False)
    return elo_p, audit_p
