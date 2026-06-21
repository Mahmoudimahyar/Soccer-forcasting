# Odds Pilot — 2022 WC Matchday 1 Data-Quality Report (2026-06-21)

## Decision: validated from EXISTING data — 0 credits spent
Before spending, I checked the repo and found the 2022 WC group-stage historical odds **already
exist** from a prior backfill: `data/processed/market_features_2022.csv` (48 matches) +
`data/raw/odds/historical_2022/` (40 raw snapshot JSONs with full book detail). Re-downloading the
16 MD1 matches would have cost ~160 credits to re-acquire a subset of data we already hold at higher
quality. Per the instruction to preserve credits and stop if redundant, I **validated the existing
data** instead. **Credits spent: 0. Odds quota remaining: 13,100.**

## Scope validated (MD1 subset)
2022 WC, group stage, **Matchday 1, 16 matches**, region `us`, market `h2h/1X2`, one pre-kickoff
snapshot per match. Output: `data/processed/odds_pilot_2022_md1.csv`.

## Data-quality results
| check | result |
|---|---|
| credits spent | **0** (existing data) |
| matches requested (MD1) | 16 |
| matches returned with odds | **16** |
| missing / invalid records | **0** |
| valid pre-kickoff records | **16/16** (`snapshot_time < commence_time`) |
| snapshot lead time | **~94.4 min** before kickoff (consistent; slightly outside the 60–90 target but safely pre-kickoff) |
| no-vig probs sum to 1 | **yes** (0 missing cells) |
| bookmaker count | **32–35 books/match** (deep) |
| raw mean overround | **1.047–1.052** (~5% margin, correctly removed by no-vig normalization) |
| match mapping / team normalization | **all 16 mapped** via `canonical_team_name` (e.g. United States, Netherlands) |
| schema consistency | consistent (`commence_time, snapshot_time, p_a/draw/b_market, market_total_goals, n_books`) |

## Verdict
**PASS — high quality.** The 2022 MD1 odds are complete, deep, leakage-safe (strictly pre-kickoff),
and the no-vig conversion is correct. They can safely enter the historical modeling table for a
market-vs-B1 evaluation. (Minor note: lead time is ~94 min, not the 60–90 target — acceptable, but
record the actual offset; a future targeted snapshot could hit 75 min if exactness matters.)

## Is a full 2022 group-stage backfill justified?
**Not needed — it already exists** (all 48 group matches in `market_features_2022.csv`). No further
2022 spend is warranted.

## Should remaining credits be preserved for live 2026?
**Yes.** Because API-Football's free plan cannot serve 2026 (seasons 2022–2024 only), **The Odds API
is the primary live-odds source for 2026**. Preserve the 13,100 credits for live 2026 pre-match/
in-play odds capture rather than re-fetching historical data we already have.

## Governance
Per instruction, the 2022 odds are **not** used to tune `candidate.py` yet — this was a data-quality
+ leakage validation only. A market-vs-B1 evaluation on the (already-present) 2022 fold is the next
analysis step, on your go-ahead.
