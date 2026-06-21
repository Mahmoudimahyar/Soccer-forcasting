# Cycle 6 — Squad / player data (lineups, market value, age, league) — 2026-06-20

User ask: extract minute-by-minute / lineup / individual-player data (age, league, value) and
see if it improves the model. Result: **a well-evidenced NULL** — player/squad data is
redundant with Elo + the market and does not improve out-of-sample.

## What was usable, and what wasn't
- **Minute-by-minute / in-play events are POST-kickoff** → leakage for a pre-match forecast.
  Usable only for a separate in-play model (different objective); excluded here.
- **Pre-match-usable = lineups + player attributes** (age, club/league, market value).

## Data obtained (free, no scraping, time-safe)
- **Transfermarkt open dataset** (dcaribou, public Cloudflare bucket, no auth; 206MB DuckDB,
  12 tables). Time-stamped `player_valuations` (→ value as-of match date, leakage-safe),
  `players.date_of_birth` (→ age), `player_club_domestic_competition_id` (→ league),
  `game_lineups` (starting XI). `scripts/squad_feature_test.py`.
- **Coverage gap that matters:** TM has lineups for **Copa America, AFCON, Asian Cup** but
  **NONE for the World Cup or Euro** (the key tournaments). Its `national_teams` value aggregate
  is current-only (not time-safe). jfjelstul squads are WC-only (≤2022, no value/club).
- Built starting-XI features for 128 TM tournament games: total/mean market value (as-of date),
  mean age, share of players in a top-5 league; all as home−away deltas.

## Results — squad/player data does NOT help
1. **Redundant with strength we already have:** corr(value_delta, elo_delta) = **0.74**;
   corr(value_delta, market favorite-margin) = **0.83**. The market already prices squad value.
2. **Beyond Elo (N=128 TM tournament games, 5-fold CV logloss):** Elo-only **0.813** vs
   Elo+squad(value,age,league) **0.834** — adding squad data is *worse* (noise/overfit).
3. **Beyond market+Elo (22 odds-matched Copa matches, 5-fold CV composite):** 0.3939 → 0.3931
   (Δ 0.0008, noise; N tiny).

This mirrors the FIFA-ranking result (cycle 2b: corr 0.78, no gain). Squad strength is the most
basic input markets price efficiently, so it carries little signal orthogonal to Elo + odds.

## Why news-scraping game-by-game was NOT pursued
- The pre-match-useful structured data (lineups, player value/age/league) is cleaner from the
  Transfermarkt dataset than from parsing free-text match reports, and it already shows no edge.
- Minute-by-minute reports are in-play (leakage). Lineup news is priced by the closing market.
- So scraping news would hit the same redundancy wall while being fragile and ToS-risky.

## Honest verdict
Player/squad data does not beat or improve on market+Elo. The genuinely orthogonal, possibly
mispriced signal (late key-player absences) is (a) priced by the closing line and (b) blocked
for WC/Euro by the lineup-data gap. **No model change.** The validated improvement remains the
cycle-4/5 market+Elo blend (beats Pinnacle close ~4-7% RPS).

## Artifacts
`scripts/squad_feature_test.py`, `data/processed/squad_features_tm.csv`,
`data/raw/transfermarkt.duckdb` (206MB, gitignored, reusable; safe to delete).
