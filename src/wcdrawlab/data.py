from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import pandas as pd


@dataclass(frozen=True)
class DataPaths:
    matches: Path
    elo: Path | None = None
    fifa: Path | None = None
    odds: Path | None = None
    venues: Path | None = None


def read_csv(path: str | Path, date_cols: Iterable[str] = ()) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, parse_dates=list(date_cols))


def validate_required_columns(df: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def assert_time_safe(feature_times: pd.Series, kickoff_times: pd.Series, label: str) -> None:
    bad = feature_times > kickoff_times
    if bad.any():
        n = int(bad.sum())
        raise ValueError(f"{label}: {n} rows leak future information.")


def asof_join_team_rating(
    matches: pd.DataFrame,
    ratings: pd.DataFrame,
    team_col: str,
    date_col: str,
    rating_team_col: str,
    rating_date_col: str,
    rating_cols: list[str],
    tolerance_days: int | None = 45,
    suffix: str = "",
) -> pd.DataFrame:
    """Join each match team to the latest rating snapshot at or before kickoff.

    This prevents leakage. It uses pandas.merge_asof by team.
    """
    left = matches[["match_id", date_col, team_col]].copy()
    left = left.sort_values([date_col, team_col])
    right = ratings[[rating_team_col, rating_date_col, *rating_cols]].copy()
    right = right.sort_values([rating_date_col, rating_team_col])

    tol = pd.Timedelta(days=tolerance_days) if tolerance_days is not None else None
    out = pd.merge_asof(
        left,
        right,
        left_on=date_col,
        right_on=rating_date_col,
        left_by=team_col,
        right_by=rating_team_col,
        direction="backward",
        tolerance=tol,
    )
    rename = {c: f"{c}{suffix}" for c in rating_cols}
    rename[rating_date_col] = f"{rating_date_col}{suffix}"
    out = out.rename(columns=rename)
    return matches.merge(out[["match_id", *rename.values()]], on="match_id", how="left")


def chronological_split(df: pd.DataFrame, date_col: str, test_start: str | pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(df[date_col], utc=True)
    test_start = pd.Timestamp(test_start)
    if test_start.tzinfo is None:
        test_start = test_start.tz_localize("UTC")
    else:
        test_start = test_start.tz_convert("UTC")
    train = df[dates < test_start].copy()
    test = df[dates >= test_start].copy()
    if train.empty or test.empty:
        raise ValueError("Chronological split produced empty train or test set.")
    return train, test
