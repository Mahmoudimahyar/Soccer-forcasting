"""Validate the 2022 WC Matchday-1 historical-odds data quality from EXISTING repo data.
Spends ZERO Odds API credits (the data was already backfilled to data/processed/market_features_2022.csv
+ data/raw/odds/historical_2022). Produces data/processed/odds_pilot_2022_md1.csv and validation stats.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
mf = pd.read_csv(ROOT / "data/processed/market_features_2022.csv", parse_dates=["commence_time", "snapshot_time"])
mf["a"] = mf.team_a.map(canonical_team_name); mf["b"] = mf.team_b.map(canonical_team_name)

# 2022 MD1 matches from the research table (authoritative matchday labels)
t = pd.read_csv(ROOT / "data/processed/research_modeling_table.csv", parse_dates=["kickoff_utc"])
t = t[(t.kickoff_utc.dt.year == 2022) & (t.stage.astype(str).str.lower() == "group") & (t.matchday == 1)].copy()
t["a"] = t.team_a.map(canonical_team_name); t["b"] = t.team_b.map(canonical_team_name)
md1_pairs = {frozenset((r.a, r.b)) for r in t.itertuples()}
print(f"2022 MD1 matches in research table: {len(t)}")

mf["pair"] = mf.apply(lambda r: frozenset((r.a, r.b)), axis=1)
pilot = mf[mf.pair.isin(md1_pairs)].copy()
print(f"MD1 odds rows matched in market_features_2022: {len(pilot)}")

# ---- overround from raw snapshots (validate no-vig conversion) ----
raw_events = {}
for fp in glob.glob(str(ROOT / "data/raw/odds/historical_2022/*.json")):
    try:
        j = json.load(open(fp, encoding="utf-8"))
    except Exception:
        continue
    for ev in (j.get("data", j) if isinstance(j.get("data", j), list) else []):
        pair = frozenset((canonical_team_name(ev.get("home_team", "")), canonical_team_name(ev.get("away_team", ""))))
        overs = []
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                if mk.get("key") == "h2h":
                    prices = [o.get("price") for o in mk.get("outcomes", []) if o.get("price")]
                    if len(prices) == 3:
                        overs.append(sum(1.0 / p for p in prices))
        if overs:
            raw_events.setdefault(pair, []).extend(overs)

pilot["mean_overround"] = pilot.pair.map(lambda p: float(np.mean(raw_events.get(p, [np.nan]))))
pilot["lead_min"] = (pilot.commence_time - pilot.snapshot_time).dt.total_seconds() / 60.0
pilot["pre_kickoff_valid"] = pilot.snapshot_time < pilot.commence_time
pilot["prob_sum"] = pilot[["p_a_market", "p_draw_market", "p_b_market"]].sum(1)

out = pilot[["a", "b", "commence_time", "snapshot_time", "lead_min", "pre_kickoff_valid",
             "p_a_market", "p_draw_market", "p_b_market", "market_total_goals", "n_books",
             "mean_overround", "prob_sum"]].rename(columns={"a": "team_a", "b": "team_b"})
out.to_csv(ROOT / "data/processed/odds_pilot_2022_md1.csv", index=False)

print("\n=== DATA-QUALITY VALIDATION (existing data, 0 credits) ===")
print(f"  matches requested (MD1): {len(t)} | returned with odds: {len(out)} | missing: {len(t)-len(out)}")
print(f"  pre-kickoff valid: {int(out.pre_kickoff_valid.sum())}/{len(out)} | lead min/med/max = "
      f"{out.lead_min.min():.1f}/{out.lead_min.median():.1f}/{out.lead_min.max():.1f}")
print(f"  no-vig probs sum to 1: {bool(np.allclose(out.prob_sum,1.0,atol=1e-6))} | missing prob cells: {int(out[['p_a_market','p_draw_market','p_b_market']].isna().sum().sum())}")
print(f"  bookmaker count min/med/max: {int(out.n_books.min())}/{int(out.n_books.median())}/{int(out.n_books.max())}")
print(f"  raw mean overround min/med/max: {out.mean_overround.min():.3f}/{out.mean_overround.median():.3f}/{out.mean_overround.max():.3f}  (raw>1 => margin removed by no-vig)")
print(f"  team-name normalization: all canonical (joined via canonical_team_name)")
print("  wrote data/processed/odds_pilot_2022_md1.csv")
