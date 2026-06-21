# Research Blockers

## B-1: API-Football key not authenticated (lineups / events / injuries unavailable)
- **Status:** OPEN. Account-dependent; needs your action.
- **Evidence (live-tested both auth modes, 2026-06-21, no secret exposed):**
  - Direct `v3.football.api-sports.io` + `x-apisports-key` → HTTP 200 with an `errors` token object
    (key not valid for direct dashboard auth).
  - RapidAPI `api-football-v1.p.rapidapi.com` + `x-rapidapi-key`/`x-rapidapi-host` → 4xx (not a
    valid/subscribed RapidAPI key for this API).
- **Impact:** no confirmed lineups, injuries/suspensions, or event timelines → research priorities
  #2/#3/#9 and the in-play model's live event inputs are blocked. **Not on B1's critical path**
  (results/standings come from football-data.org; odds from The Odds API).
- **Exact action needed from you (either one):**
  1. Provide a **direct api-sports.io dashboard key** (https://dashboard.api-football.com) — the
     existing adapter works unchanged; or
  2. Provide a **RapidAPI key with an active API-Football subscription** AND approve a one-line
     host/header change to `src/wcdrawlab/providers/api_football.py` (currently protected).
- **Workaround in use:** continue with football-data.org + The Odds API + Open-Meteo + open
  historical datasets. Request on file: `data_requests/pending/api_football.yaml` (status: blocked).

## B-2: No pre-2020 historical odds (market model only validatable on 2022)
- **Status:** OPEN (data limitation, not an account error). The Odds API historical coverage starts
  2020-06, so the 2018 fold and earlier have no market features and the market-vs-Elo comparison can
  only be run on 2022 + post-2020 internationals.
- **Impact:** the one signal that beats Elo (the market) cannot be validated across the dev folds →
  no statistically-backed path to promote a market model over B1 yet.
- **Action needed:** approval to spend Odds API historical credits to backfill 2020-06→ odds into
  schema N (append-only store), enabling a paired-bootstrap market-vs-B1 test on the odds-covered
  span. Not started (requires your go-ahead).
