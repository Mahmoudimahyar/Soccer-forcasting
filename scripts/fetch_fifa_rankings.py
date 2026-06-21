"""Fetch open FIFA world ranking history (Dato-Futbol/fifa-ranking, 1992-2024, monthly)
and normalize to the project schema. Free, no account; CC-style open dataset on GitHub.

Output: data/processed/fifa_rankings.csv  (team, release_date, fifa_points, fifa_rank)
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.ingest import canonical_team_name  # noqa: E402

URL = "https://raw.githubusercontent.com/Dato-Futbol/fifa-ranking/master/ranking_fifa_historical.csv"
RAW = ROOT / "data" / "raw" / "fifa_ranking_dato.csv"
OUT = ROOT / "data" / "processed" / "fifa_rankings.csv"

EXTRA = {
    "IR Iran": "Iran", "Korea DPR": "North Korea", "Korea Republic": "Korea Republic",
    "Republic of Ireland": "Ireland",
    "China PR": "China", "USA": "United States", "Czech Republic": "Czechia",
    "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
    "Cabo Verde": "Cape Verde", "Türkiye": "Turkey", "Turkiye": "Turkey",
    "Congo DR": "Congo DR", "DR Congo": "Congo DR",
}


def canon(n: str) -> str:
    return EXTRA.get(str(n).strip(), canonical_team_name(n))


def main():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if not RAW.exists():
        with urllib.request.urlopen(URL, timeout=60) as r:
            RAW.write_bytes(r.read())
    df = pd.read_csv(RAW)
    df = df.rename(columns={"total_points": "fifa_points", "date": "release_date"})
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce", utc=True)
    df["team"] = df["team"].map(canon)
    df = df.dropna(subset=["release_date", "fifa_points"])
    # derive rank within each release (points descending)
    df["fifa_rank"] = df.groupby("release_date")["fifa_points"].rank(ascending=False, method="min").astype(int)
    out = df[["team", "release_date", "fifa_points", "fifa_rank"]].sort_values(["release_date", "fifa_rank"])
    out.to_csv(OUT, index=False)
    print("releases:", out["release_date"].nunique(),
          "| range:", out["release_date"].min().date(), "->", out["release_date"].max().date())
    print("rows:", len(out), "| teams:", out["team"].nunique())
    # coverage check vs WC teams in the modeling table
    tbl = ROOT / "data" / "processed" / "research_modeling_table.csv"
    if tbl.exists():
        t = pd.read_csv(tbl)
        wc_teams = set(t["team_a"]) | set(t["team_b"])
        fifa_teams = set(out["team"])
        missing = sorted(wc_teams - fifa_teams)
        print(f"WC teams covered by FIFA ranking: {len(wc_teams & fifa_teams)}/{len(wc_teams)}")
        if missing:
            print("  missing:", missing)
    print("wrote:", OUT)


if __name__ == "__main__":
    main()
