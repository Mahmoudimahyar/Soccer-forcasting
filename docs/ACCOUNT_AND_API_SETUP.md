# Account and API Setup

This project works in two layers:

1. **Research / historical data** — can begin without paid accounts.
2. **Live match operations** — requires API keys for the requested live feeds.

## Create these accounts first

Create accounts and add the corresponding values to your local `.env` file. Do **not** paste keys into Claude Code, commit them to Git, or put them in screenshots.

| Provider | Why it is needed | Environment variable | When needed |
|---|---|---|---|
| API-Football | fixtures, live results, standings, lineups, events, injuries, match statistics | `API_FOOTBALL_KEY` | Needed for live match updates |
| The Odds API | timestamped 1X2 odds, totals, handicaps, bookmaker consensus and line movement | `ODDS_API_KEY` | Needed for market-aware forecasts |
| football-data.org | secondary fixture/result/table validation and fallback | `FOOTBALL_DATA_KEY` | Recommended for live reliability |

## Create later

| Provider | Why it is needed | Environment variables | When needed |
|---|---|---|---|
| Kalshi demo | paper/demo market integration and orderbook testing | `KALSHI_ENV=demo`, `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH` | Only after the forecasting pipeline is stable |

Keep these settings unchanged while research is underway:

```bash
KALSHI_ENABLE_LIVE_TRADING=false
TRADING_MODE=paper
```

## No account required

- Open-Meteo forecast API
- Internal Elo engine
- Public historical repositories configured by the project
- Static venue coordinate tables

## Safe configuration audit

Claude Code may report only `SET` or `MISSING` for required environment-variable names. It must never print, inspect, copy, or commit secret values. The intended audit output is a status table, not a dump of `.env`.

## Minimal `.env` pattern

```bash
API_FOOTBALL_KEY=
ODDS_API_KEY=
FOOTBALL_DATA_KEY=

KALSHI_ENV=demo
KALSHI_API_KEY_ID=
KALSHI_PRIVATE_KEY_PATH=
KALSHI_ENABLE_LIVE_TRADING=false
```

## Rules for adding another source

Before an additional API or scraper is added, Claude Code must create a request under `data_requests/pending/` using `data_requests/TEMPLATE.yaml`. The request must state the predicted signal, historical and live coverage, account/cost requirements, terms URL, latency, rate limit, leakage controls, and storage/test plan.
