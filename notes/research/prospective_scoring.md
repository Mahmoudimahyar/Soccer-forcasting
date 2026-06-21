# Prospective Scoring Loop (model vs market, live)

The genuine forward test: freeze a forecast before kickoff, then grade it after the result.
Built free, reusable, leakage-clean. One command:

```
python scripts/prospective_scorecard.py            # refresh live results + score
python scripts/prospective_scorecard.py --no-refresh  # score against cached results
```

## How it works
1. **Ledger** (`data/processed/forecast_ledger.csv`) — append-only, **first-write-wins**. Each
   run appends the current pre-kickoff forecasts (model B7 + market consensus) from
   `forecast_2026_market_anchored.csv` for any match not already recorded. A match's forecast is
   never overwritten once stored, so it remains a true pre-kickoff prediction.
2. **Scorer** — re-fetches the latest football-data.org results and grades every ledger forecast
   whose match has FINISHED: per-match and mean RPS / log-loss for the **model** and the
   **market**, and which one is ahead. Output: `outputs/research/prospective_scorecard.csv`.

## Refreshing the forecasts before scoring (optional, when new matchdays approach)
To re-forecast remaining matches with the latest odds/standings before they kick off:
```
python scripts/fetch_footballdata_2026.py    # latest results/standings (free)
python scripts/fetch_odds_2026.py            # latest odds snapshot (~6 Odds API credits)
python scripts/build_research_table.py
python scripts/build_market_features.py
python scripts/forecast_2026.py
python scripts/market_anchored_forecast.py
python scripts/prospective_scorecard.py      # freezes any newly-upcoming match, scores finished
```
Only matches not yet in the ledger get a fresh frozen forecast; already-recorded (pre-kickoff)
forecasts are preserved.

## Current state (2026-06-20)
Ledger seeded with **39 frozen forecasts** (15 MD2 + 24 MD3). None have finished yet — they
begin 2026-06-20 evening. The scorecard will populate as matches play. Re-run after each
matchday to watch model-vs-market accumulate.

## Companion (backward view)
`scripts/prequential_2026.py` already scores model / Elo / prior over ALL finished 2026 matches
(no market, since we have no stored pre-kickoff odds for matches already played before today).
Current read: plain Elo leads on RPS/log-loss; the calibrated candidate leads on draw
calibration. See `notes/research/prequential_2026.md`.

## What "success" would look like
Over a meaningful number of finished forecasts (say 20+), the model's mean RPS/log-loss at or
below the market's. Until then, no edge is claimed — the market consensus remains the headline
forecast and the model's disagreements are unproven hypotheses.
