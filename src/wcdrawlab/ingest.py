from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping
import json
import urllib.request
import pandas as pd


@dataclass(frozen=True)
class SourceSpec:
    name: str
    url: str
    destination: str
    kind: str
    notes: str = ""


DEFAULT_SOURCES: dict[str, SourceSpec] = {
    "international_results": SourceSpec(
        name="international_results",
        url="https://raw.githubusercontent.com/martj42/international_results/master/results.csv",
        destination="data/raw/international_results.csv",
        kind="match_results",
        notes="General men's international match results. Does not include World Cup group labels.",
    ),
    "jf_worldcup_matches": SourceSpec(
        name="jf_worldcup_matches",
        url="https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/matches.csv",
        destination="data/raw/jf_worldcup_matches.csv",
        kind="worldcup_matches",
        notes="Structured FIFA World Cup match-level data. Column names may change upstream; use normalize_worldcup_matches().",
    ),
    "jf_worldcup_tournaments": SourceSpec(
        name="jf_worldcup_tournaments",
        url="https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/tournaments.csv",
        destination="data/raw/jf_worldcup_tournaments.csv",
        kind="worldcup_metadata",
        notes="Structured tournament metadata for the jfjelstul/worldcup dataset.",
    ),
}


def download_file(url: str, destination: str | Path, overwrite: bool = False, timeout: int = 30) -> Path:
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return dest
    with urllib.request.urlopen(url, timeout=timeout) as response:
        content = response.read()
    dest.write_bytes(content)
    return dest


def download_default_sources(root: str | Path = ".", names: Iterable[str] | None = None, overwrite: bool = False) -> list[Path]:
    root = Path(root)
    selected = list(names) if names is not None else list(DEFAULT_SOURCES)
    paths: list[Path] = []
    for name in selected:
        if name not in DEFAULT_SOURCES:
            raise KeyError(f"Unknown source {name!r}. Known: {sorted(DEFAULT_SOURCES)}")
        spec = DEFAULT_SOURCES[name]
        paths.append(download_file(spec.url, root / spec.destination, overwrite=overwrite))
    return paths


def write_source_registry(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: spec.__dict__ for k, spec in DEFAULT_SOURCES.items()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


TEAM_ALIASES = {
    "USA": "United States",
    "United States of America": "United States",
    "USMNT": "United States",
    "Czech Republic": "Czechia",
    "DR Congo": "Congo DR",
    "Democratic Republic of the Congo": "Congo DR",
    "Bosnia and Herzegovina": "Bosnia",
    "Cabo Verde": "Cape Verde",
    "Curaçao": "Curacao",
    "Türkiye": "Turkey",
    "South Korea": "Korea Republic",
}


def canonical_team_name(name: str) -> str:
    if pd.isna(name):
        return name
    text = str(name).strip()
    return TEAM_ALIASES.get(text, text)


def canonicalize_team_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for c in columns:
        if c in out.columns:
            out[c] = out[c].map(canonical_team_name)
    return out


def normalize_international_results(results: pd.DataFrame) -> pd.DataFrame:
    """Normalize martj42/international_results-style data into the project schema.

    This dataset is useful for training and for custom Elo construction, but it does
    not carry World Cup group labels. Use a structured World Cup dataset for
    group-state backtests.
    """
    required = {"date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"}
    missing = required - set(results.columns)
    if missing:
        raise ValueError(f"international_results missing expected columns: {missing}")
    df = results.copy()
    df["kickoff_utc"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df["match_id"] = [f"intl_{i}" for i in range(len(df))]
    df = df.rename(
        columns={
            "home_team": "team_a",
            "away_team": "team_b",
            "home_score": "goals_a",
            "away_score": "goals_b",
            "city": "venue_city",
            "country": "venue_country",
        }
    )
    df["stage"] = df.get("stage", "unknown")
    df["group"] = pd.NA
    df["matchday"] = pd.NA
    keep = [
        "match_id", "kickoff_utc", "tournament", "stage", "group", "matchday", "team_a", "team_b",
        "goals_a", "goals_b", "neutral", "venue_city", "venue_country",
    ]
    df = df[[c for c in keep if c in df.columns]]
    return canonicalize_team_columns(df, ["team_a", "team_b"])


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    cols = set(columns)
    for c in candidates:
        if c in cols:
            return c
    return None


def normalize_worldcup_matches(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize a structured World Cup match dataset into the project schema.

    This function is deliberately flexible because public datasets change column names.
    It supports common columns from structured World Cup datasets and will fail loudly
    with a helpful message when a required mapping cannot be inferred.
    """
    df = raw.copy()
    colmap_candidates: Mapping[str, list[str]] = {
        "match_id": ["match_id", "key_id", "id", "match"],
        "kickoff_utc": ["kickoff_utc", "match_date", "date", "datetime"],
        "tournament": ["tournament", "tournament_name", "world_cup", "competition"],
        "stage": ["stage", "stage_name", "round", "phase"],
        "group": ["group", "group_name", "group_stage", "group_id"],
        "team_a": ["home_team_name", "home_team", "team_a", "team1", "home"],
        "team_b": ["away_team_name", "away_team", "team_b", "team2", "away"],
        "goals_a": ["home_team_score", "home_score", "goals_a", "score_a", "team1_score"],
        "goals_b": ["away_team_score", "away_score", "goals_b", "score_b", "team2_score"],
        "venue": ["stadium_name", "stadium", "venue", "city_name", "city"],
    }
    inferred: dict[str, str] = {}
    missing: list[str] = []
    for target, candidates in colmap_candidates.items():
        source = _first_existing(df.columns, candidates)
        if source is None and target not in {"group", "venue"}:
            missing.append(f"{target}: one of {candidates}")
        elif source is not None:
            inferred[target] = source
    if missing:
        raise ValueError("Could not infer required World Cup match columns:\n" + "\n".join(missing))

    out = pd.DataFrame()
    for target, source in inferred.items():
        out[target] = df[source]
    out["kickoff_utc"] = pd.to_datetime(out["kickoff_utc"], errors="coerce", utc=True)
    if "match_id" not in out or out["match_id"].isna().any():
        out["match_id"] = [f"wc_{i}" for i in range(len(out))]
    out["neutral"] = True
    if "group" not in out:
        out["group"] = pd.NA
    if "venue" not in out:
        out["venue"] = pd.NA
    out["matchday"] = infer_group_matchday(out)
    return canonicalize_team_columns(out, ["team_a", "team_b"])


def infer_group_matchday(matches: pd.DataFrame) -> pd.Series:
    """Infer 1/2/3 group matchday from chronological group order.

    For normal four-team groups, matches 1-2 are MD1, 3-4 MD2, 5-6 MD3.
    Non-group or non-standard groups return NA.
    """
    if "group" not in matches.columns:
        return pd.Series(pd.NA, index=matches.index, dtype="Int64")
    out = pd.Series(pd.NA, index=matches.index, dtype="Int64")
    group_matches = matches[matches["group"].notna()].sort_values(["group", "kickoff_utc", "match_id"])
    for group, g in group_matches.groupby("group", sort=False):
        if len(g) == 6:
            md = [1, 1, 2, 2, 3, 3]
            out.loc[g.index] = md
        elif len(g) > 0:
            # Best effort: every two matches increments a matchday.
            out.loc[g.index] = ((range(len(g))))
    if not out.dropna().empty and not pd.api.types.is_integer_dtype(out.dropna()):
        out = out.astype("Int64")
    return out


def load_seed_2026(root: str | Path = ".") -> pd.DataFrame:
    path = Path(root) / "data" / "seed" / "worldcup_2026_seed_matches.csv"
    return pd.read_csv(path, parse_dates=["kickoff_utc"])
