from __future__ import annotations

from pathlib import Path
import math
import pandas as pd
from wcdrawlab.features import add_basic_outcome_columns, build_pre_match_group_state


def filter_worldcup_group_stage(matches: pd.DataFrame, year_min: int = 1998, year_max: int = 2022) -> pd.DataFrame:
    df = matches.copy()
    if "kickoff_utc" in df.columns:
        years = pd.to_datetime(df["kickoff_utc"], utc=True).dt.year
        df = df[(years >= year_min) & (years <= year_max)]
    if "stage" in df.columns:
        stage = df["stage"].astype(str).str.lower()
        df = df[stage.str.contains("group", na=False) | (df.get("group", pd.Series(index=df.index, dtype=object)).notna())]
    return df


def draw_rate_by_tournament(matches: pd.DataFrame) -> pd.DataFrame:
    df = add_basic_outcome_columns(matches)
    if "year" not in df.columns:
        df["year"] = pd.to_datetime(df["kickoff_utc"], utc=True).dt.year
    out = df.groupby("year").agg(
        matches=("match_id", "count"),
        draws=("is_draw", "sum"),
    ).reset_index()
    out["draw_rate"] = out["draws"] / out["matches"]
    return out


def draw_rate_by_matchday(matches: pd.DataFrame) -> pd.DataFrame:
    df = add_basic_outcome_columns(matches)
    if "matchday" not in df.columns:
        raise ValueError("matches must contain matchday")
    out = df[df["matchday"].notna()].groupby("matchday").agg(
        matches=("match_id", "count"), draws=("is_draw", "sum")
    ).reset_index()
    out["draw_rate"] = out["draws"] / out["matches"]
    return out


def draws_per_group(matches: pd.DataFrame) -> pd.DataFrame:
    df = add_basic_outcome_columns(matches)
    if "year" not in df.columns:
        df["year"] = pd.to_datetime(df["kickoff_utc"], utc=True).dt.year
    group_cols = ["year", "group"]
    out = df[df["group"].notna()].groupby(group_cols).agg(
        matches=("match_id", "count"), draws=("is_draw", "sum")
    ).reset_index()
    return out[out["matches"] > 0]


def draws_per_group_distribution(matches: pd.DataFrame) -> pd.DataFrame:
    dpg = draws_per_group(matches)
    out = dpg.groupby("draws").agg(groups=("group", "count")).reset_index()
    out["share"] = out["groups"] / out["groups"].sum()
    return out


def conditional_by_prior_group_draws(matches: pd.DataFrame) -> pd.DataFrame:
    df = add_basic_outcome_columns(matches)
    df = build_pre_match_group_state(df)
    out = df.groupby("prior_group_draws").agg(
        matches=("match_id", "count"), draws=("is_draw", "sum")
    ).reset_index()
    out["draw_rate"] = out["draws"] / out["matches"]
    return out


def binomial_group_draw_distribution(p: float, n: int = 6) -> pd.DataFrame:
    rows = []
    for k in range(n + 1):
        prob = math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))
        rows.append({"draws": k, "probability": prob})
    return pd.DataFrame(rows)


def write_truth_tables(matches: pd.DataFrame, outdir: str | Path) -> dict[str, Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tables = {
        "draw_rate_by_tournament": draw_rate_by_tournament(matches),
        "draw_rate_by_matchday": draw_rate_by_matchday(matches),
        "draws_per_group": draws_per_group(matches),
        "draws_per_group_distribution": draws_per_group_distribution(matches),
        "conditional_by_prior_group_draws": conditional_by_prior_group_draws(matches),
        "binomial_p_024": binomial_group_draw_distribution(0.24),
        "binomial_p_247": binomial_group_draw_distribution(0.247),
    }
    paths = {}
    for name, table in tables.items():
        path = outdir / f"{name}.csv"
        table.to_csv(path, index=False)
        paths[name] = path
    return paths
