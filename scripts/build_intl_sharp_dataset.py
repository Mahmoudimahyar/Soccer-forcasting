"""Merge the sharp (closing-line + Pinnacle) odds onto the already-matched intl dataset
(which carries Elo + outcome + the T-90min consensus). Output: intl_market_sharp.csv
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


def main():
    base = pd.read_csv(PROC / "intl_market_dataset.csv", parse_dates=["kickoff_utc"])
    sharp = pd.read_csv(PROC / "intl_odds_sharp.csv")
    sharp = sharp.rename(columns={"home": "team_a", "away": "team_b", "n_books": "n_books_close"})
    keep = ["sport", "commence_time", "team_a", "team_b", "n_books_close", "has_pinnacle",
            "cons_a", "cons_d", "cons_b", "pin_a", "pin_d", "pin_b"]
    base["commence_time"] = base["kickoff_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    m = base.merge(sharp[keep], on=["sport", "commence_time", "team_a", "team_b"], how="inner")
    m.to_csv(PROC / "intl_market_sharp.csv", index=False)
    print(f"base={len(base)} sharp={len(sharp)} merged={len(m)} | with_pinnacle={int(m['has_pinnacle'].sum())}")
    # how much sharper is the closing consensus vs the T-90 consensus? (Brier-ish self-check)
    print("median books: T-90 n/a here; close=", int(m["n_books_close"].median()))
    print("wrote:", PROC / "intl_market_sharp.csv")


if __name__ == "__main__":
    main()
