"""One-shot audit of downloaded public datasets for the data inventory report.

Prints coverage, schema, World Cup coverage by year, anomalies, duplicates, and
group-stage reconstructability. Read-only; does not modify any data.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def line(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def audit_international() -> None:
    line("martj42/international_results.csv")
    df = pd.read_csv(RAW / "international_results.csv")
    print("shape:", df.shape)
    print("columns:", list(df.columns))
    d = pd.to_datetime(df["date"], errors="coerce")
    print("date range:", d.min(), "->", d.max())
    print("n rows with unparseable date:", int(d.isna().sum()))
    print("null home_score:", int(df["home_score"].isna().sum()),
          "null away_score:", int(df["away_score"].isna().sum()))
    print("exact duplicate rows:", int(df.duplicated().sum()))
    key = ["date", "home_team", "away_team"]
    print("dupe on (date,home,away):", int(df.duplicated(subset=key).sum()))
    print("n distinct tournaments:", df["tournament"].nunique())
    print("top tournaments:\n", df["tournament"].value_counts().head(12).to_string())
    wc = df[df["tournament"] == "FIFA World Cup"].copy()
    wc["year"] = pd.to_datetime(wc["date"], errors="coerce").dt.year
    print("\nFIFA World Cup rows total:", len(wc))
    print("WC matches by year (recent):\n",
          wc[wc.year >= 2010].groupby("year").size().to_string())
    for yr in (2018, 2022, 2026):
        sub = wc[wc.year == yr]
        print(f"\n--- WC {yr}: {len(sub)} matches ---")
        if len(sub):
            print("date span:", pd.to_datetime(sub['date']).min().date(),
                  "->", pd.to_datetime(sub['date']).max().date())
            print(sub[["date", "home_team", "away_team", "home_score",
                       "away_score", "neutral"]].head(8).to_string(index=False))
    # 2026 full dump (we are mid-tournament)
    sub26 = wc[wc.year == 2026].sort_values("date")
    if len(sub26):
        line("FULL 2026 WORLD CUP ROWS IN martj42 (no group labels)")
        print(sub26[["date", "home_team", "away_team", "home_score",
                     "away_score", "neutral"]].to_string(index=False))


def audit_jf() -> None:
    line("jfjelstul/worldcup matches.csv")
    df = pd.read_csv(RAW / "jf_worldcup_matches.csv")
    print("shape:", df.shape)
    print("columns:", list(df.columns))
    for col in ("tournament_id", "tournament_name", "stage_name", "group_name",
                "group_stage", "knockout_stage", "match_date", "match_name"):
        if col in df.columns:
            vals = df[col].dropna().unique()
            print(f"  {col}: {len(vals)} distinct; sample={list(vals[:6])}")
    # year coverage
    if "match_date" in df.columns:
        yr = pd.to_datetime(df["match_date"], errors="coerce").dt.year
        print("year range:", int(yr.min()), "->", int(yr.max()))
        print("matches by tournament year:\n", yr.value_counts().sort_index().to_string())


def audit_jf_tournaments() -> None:
    line("jfjelstul/worldcup tournaments.csv")
    df = pd.read_csv(RAW / "jf_worldcup_tournaments.csv")
    print("shape:", df.shape)
    print("columns:", list(df.columns))
    cols = [c for c in ("tournament_id", "tournament_name", "year", "host_country",
                        "count_teams") if c in df.columns]
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    try:
        audit_international()
    except Exception as e:  # noqa: BLE001
        print("international audit failed:", e, file=sys.stderr)
    try:
        audit_jf()
    except Exception as e:  # noqa: BLE001
        print("jf matches audit failed:", e, file=sys.stderr)
    try:
        audit_jf_tournaments()
    except Exception as e:  # noqa: BLE001
        print("jf tournaments audit failed:", e, file=sys.stderr)
