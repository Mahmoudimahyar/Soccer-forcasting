# Live Data Integration — 2026-06-20

API keys were supplied. Summary of what is now wired, the new findings, and what changed.

## Keys / providers
| Provider | Env | Status | Use |
|---|---|---|---|
| The Odds API | `ODDS_API_KEY` | ✅ working (494/500 credits left) | Real market odds → B6, market features, edges |
| football-data.org | `FOOTBALL_DATA_KEY` | ✅ working | Authoritative 2026 groups/matchday + freshest results |
| API-Football | `API_FOOTBALL_KEY` | ❌ blocked (RapidAPI-style key vs adapter's direct host) | in-play/lineups (later) — see `data_requests/pending/api_football.yaml` |
| Kalshi demo | — | absent (later/demo only) | unchanged; live trading stays off |

**Security:** keys are in `.env.example`, which is NOT gitignored. Recommend moving them to
`.env` and restoring `.env.example` to blank placeholders.

## The Odds API (baseline B6 is now live for 2026)
- `scripts/fetch_odds_2026.py` → raw snapshot `data/raw/odds/odds_fifa_world_cup_2026-06-20.json`
  (sport `soccer_fifa_world_cup`, 40 events, up to 48 books, h2h + totals, 6 credits used).
- `scripts/build_market_features.py` → `data/processed/market_features_2026.csv`: per-match
  no-vig consensus (median across books) + totals line, mapped to fixtures by date+pair.
  **39/39 upcoming matches now have market prices.**
- Historical 2018/2022 odds are not on the free tier, so B6 stays out of the backtest folds;
  it is a **live, prospective** benchmark for the remaining 2026 matches.

## football-data.org (authoritative 2026 source)
- `scripts/fetch_footballdata_2026.py` → `data/processed/results_2026_footballdata.csv`.
- **Validated: 12/12 reconstructed groups identical** to the earlier seed-anchored
  reconstruction — confirms the table's 2026 structure was correct.
- The build now uses it for 2026 group/matchday/results (replacing the reconstruction) and
  supplements the martj42 Elo history with the 4 freshest finished results martj42 still lagged.
- Result freshness: **33 finished group matches** (24 MD1 + 9 MD2) vs martj42's 28.
- Historical folds (2018/2022) are byte-identical before/after — only 2026 changed. The locked
  2026-MD1 fold improved purely from authoritative data (logloss 1.16 → 1.05). 45 tests pass.

## Model vs market (the real test now available)
On the 39 upcoming matches:
- **Draws: model 0.204 vs market 0.216** mean (model bias −0.012) — the model is now slightly
  *under* the market on draws. Close, but no evidence the model finds extra draw value.
- **Favorites: model still under-confident** (mean edge −0.022 when market p>0.6), much smaller
  than the free-data-only gap.
- Biggest disagreements (model vs market, a/d/b %):
  Czechia–Mexico 11/18/70 vs 27/26/47 · Croatia–Ghana 79/13/8 vs 59/25/16 ·
  Egypt–Iran 28/28/45 vs 45/30/25 · Japan–Sweden 64/20/16 vs 45/28/27 · Belgium–Iran 52/25/23 vs 67/20/12.
  These are recorded as **prospective hypotheses** — to be scored after the matches, not acted on.

## Refreshed forecasts
- `outputs/research/forecasts/forecast_2026_md2_md3.csv` — model (B7) probs + uncertainty (15 MD2, 24 MD3).
- `outputs/research/forecasts/forecast_2026_market_anchored.csv` — **market-primary** forecast
  (market consensus where odds exist, model otherwise) + per-match edges. This is the headline.
- `outputs/research/forecasts/advancement_2026_market.csv` — market-anchored advancement (20k sims).
  Near-locks: Mexico, Canada, Switzerland, USA, Germany, Netherlands, France, Argentina, Colombia, England.

## Honest verdict (updated)
We now have the market benchmark for 2026. The model tracks the market on draws and is close on
favorites, but **does not demonstrate an edge over the market** — exactly the bar the project
sets before claiming "good." The defensible forecast is the **market consensus** for upcoming
matches; the model's disagreements are hypotheses to score prospectively. Next real test: after
each match, log model vs market vs outcome (RPS/log-loss/CLV) to see if the model adds anything.

## Reproduce
```
python scripts/fetch_odds_2026.py          # real odds snapshot (uses ODDS_API_KEY)
python scripts/fetch_footballdata_2026.py  # authoritative 2026 results (FOOTBALL_DATA_KEY)
python scripts/build_research_table.py     # rebuild table (now football-data 2026)
python scripts/build_market_features.py    # no-vig consensus -> market features
python scripts/forecast_2026.py            # model forecasts + advancement
python scripts/market_anchored_forecast.py # market-primary forecast + edges
```
