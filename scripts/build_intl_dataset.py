"""Join the international pre-kickoff odds to martj42 results + time-safe Elo, producing a
leakage-safe modeling dataset for the 'can we beat the market' test.

Orientation is anchored to the ODDS home team (= team_a): market probs are [p_a,p_draw,p_b]
with a = odds home; elo_delta = elo_before(home) - elo_before(away); outcome A/D/B from the
actual result aligned to odds-home. Match to martj42 by (date +-1d, team pair).
Output: data/processed/intl_market_dataset.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_research_table import build_elo_history, elo_before, canon  # noqa: E402

RAW = ROOT / "data" / "processed" / "intl_odds_raw.csv"
RESULTS = ROOT / "data" / "raw" / "international_results.csv"
OUT = ROOT / "data" / "processed" / "intl_market_dataset.csv"


def main():
    odds = pd.read_csv(RAW)
    odds["home"] = odds["home"].map(canon)
    odds["away"] = odds["away"].map(canon)
    odds["kickoff"] = pd.to_datetime(odds["commence_time"], utc=True)
    odds["date"] = odds["kickoff"].dt.normalize()

    res = pd.read_csv(RESULTS)
    res["date"] = pd.to_datetime(res["date"], errors="coerce", utc=True).dt.normalize()
    res = res.dropna(subset=["date", "home_score", "away_score"])
    res["t1"] = res["home_team"].map(canon)
    res["t2"] = res["away_team"].map(canon)
    # index results by (pair) -> list of (date, t1, gа, gb)
    from collections import defaultdict
    by_pair = defaultdict(list)
    for r in res.itertuples(index=False):
        by_pair[frozenset((r.t1, r.t2))].append((r.date, r.t1, int(r.home_score), int(r.away_score)))

    hist = build_elo_history()

    rows = []
    unmatched = 0
    for o in odds.itertuples(index=False):
        cands = by_pair.get(frozenset((o.home, o.away)), [])
        best = None
        for (d, t1, ga, gb) in cands:
            if abs((d - o.date).days) <= 1:
                best = (d, t1, ga, gb); break
        if best is None:
            unmatched += 1
            continue
        d, t1, ga, gb = best
        # align outcome to odds-home
        if t1 == o.home:
            g_home, g_away = ga, gb
        else:
            g_home, g_away = gb, ga
        outcome = "A" if g_home > g_away else "D" if g_home == g_away else "B"
        ea = elo_before(hist, o.home, o.kickoff)
        eb = elo_before(hist, o.away, o.kickoff)
        rows.append({
            "sport": o.sport, "kickoff_utc": o.kickoff, "team_a": o.home, "team_b": o.away,
            "p_a_market": o.p_a_market, "p_draw_market": o.p_draw_market, "p_b_market": o.p_b_market,
            "n_books": o.n_books, "elo_a": ea, "elo_b": eb, "elo_delta": ea - eb,
            "abs_elo_delta": abs(ea - eb), "goals_a": g_home, "goals_b": g_away, "outcome": outcome,
        })
    df = pd.DataFrame(rows).sort_values("kickoff_utc").reset_index(drop=True)
    df.to_csv(OUT, index=False)
    print(f"odds rows: {len(odds)} | matched: {len(df)} | unmatched: {unmatched}")
    print("by sport:\n", df.groupby("sport").size().to_string())
    print("date range:", df["kickoff_utc"].min(), "->", df["kickoff_utc"].max())
    print("outcome dist:", df["outcome"].value_counts(normalize=True).round(3).to_dict())
    print("market draw rate vs actual:", round(df["p_draw_market"].mean(), 3),
          "vs", round((df["outcome"] == "D").mean(), 3))
    print("wrote:", OUT)


if __name__ == "__main__":
    main()
