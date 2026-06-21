from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.pipeline import build_features, run_walkforward_backtest


def main():
    matches = pd.read_csv(ROOT / "data" / "seed" / "worldcup_2026_seed_matches.csv", parse_dates=["kickoff_utc"])
    elo = pd.read_csv(ROOT / "data" / "seed" / "seed_ratings_2026.csv", parse_dates=["rating_date"])
    odds = pd.read_csv(ROOT / "data" / "seed" / "sample_odds_2026.csv", parse_dates=["snapshot_time"])
    features = build_features(matches, elo=elo, odds=odds)
    out_features = ROOT / "outputs" / "seed_2026_features.csv"
    out_features.parent.mkdir(exist_ok=True)
    features.to_csv(out_features, index=False)
    print(f"Feature table written: {out_features}")

    # This backtest is a smoke test only: the seed data is partial and uses demo ratings/odds.
    result = run_walkforward_backtest(features, test_start="2026-06-16", outdir=ROOT / "outputs" / "seed_backtest")
    print(result.metrics.to_string(index=False))


if __name__ == "__main__":
    main()
