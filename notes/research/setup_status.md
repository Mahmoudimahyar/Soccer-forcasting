# Setup Status — Safe Configuration Audit (Tier-1 refresh, 2026-06-20)

One-way SET/MISSING check only. **No secret values are read, printed, or stored.** Live trading
stays disabled: `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`.

| Variable | Status | Provider / account | Needed | Capability blocked until configured |
|---|---|---|---|---|
| `API_FOOTBALL_KEY` | **SET** but **NOT WORKING** | API-Football — must be a **direct** key from dashboard.api-football.com (the supplied key is a RapidAPI-type key, rejected by the in-repo adapter's direct host) | Later (in-play, Tier 4) | Live lineups / events / in-play stats. Not on the Tier-1 critical path. |
| `ODDS_API_KEY` | **SET** (paid 20K plan) | The Odds API | Now | ✅ Working — live + historical odds (B6, market features, beat-market analysis). |
| `FOOTBALL_DATA_KEY` | **SET** | football-data.org | Now | ✅ Working — authoritative 2026 results/standings/schedule. |
| `KALSHI_ENV` | **SET** (=demo) | Kalshi demo | Later | Paper/demo market mapping (Tier 5+). |
| `KALSHI_API_KEY_ID` | **MISSING** | Kalshi **demo** account | Later | Demo market-data access; not needed until forecasting + paper replay proven. |
| `KALSHI_PRIVATE_KEY_PATH` | **MISSING** | Kalshi **demo** key file | Later | Signing demo requests. |
| `KALSHI_ENABLE_LIVE_TRADING` | **SET** (=false) | — | Never (research) | Must remain `false`. No action. |

## Accounts needed NOW for live data
- **The Odds API** → ✅ configured and working (paid plan).
- **football-data.org** → ✅ configured and working.
- **API-Football** → ⚠️ key present but wrong type; needs a **direct api-sports.io key**. Required
  only when in-play (Tier 4) work begins, not for Tier 1.

## Needed LATER
- **Kalshi demo** (`KALSHI_ENV`, `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`) — after the
  forecasting + paper-replay system is proven. Keep `KALSHI_ENABLE_LIVE_TRADING=false`.

## Security note (unchanged)
Keys currently live in `.env.example`, which is NOT gitignored (only `.env` is). Recommend moving
secrets to `.env` and restoring `.env.example` to blank placeholders. These files are protected and
are not edited by this agent.
