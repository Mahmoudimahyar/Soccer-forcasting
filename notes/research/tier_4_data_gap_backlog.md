# Tier 4 Data-Gap Backlog (research-only; no provider added, nothing scraped)

Derived from the 2022 in-play results: the binding constraint is **feature sparsity** (M3 next-goal
hazard failed vs base rate; sub-impact and red-card targets unmodelable). Ranked by priority score
(benefit × feasibility ÷ risk). Data requests are created/referenced; none implemented.

| # | data gap | helps | hist. avail | live avail | legal/terms | cost | account | leakage risk | complexity | priority |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Event-level xG + shots feed** | in-play, next-event, xG | StatsBomb open (free, NC) | paid (Opta/Sportradar/StatsBomb API) | med (NC license) | free hist / $$ live | sign-off | med (must time-gate) | med | **highest** |
| 2 | **Confirmed lineups + benches + injuries** | pre-match, in-play, sub-impact | StatsBomb / API-Football 2022-24 (free) | API-Football Pro (~$25-30/mo) | low | low | yes | high (release-time gating) | med | high |
| 3 | **Multi-competition historical event data (volume)** | all in-play/next-event | StatsBomb open + others | n/a | med | free | sign-off | low | med-high | high |
| 4 | **Substitutions w/ player IDs + positions/formations** | in-play, sub-impact | StatsBomb / API-Football | API-Football Pro | low | low | yes | med | med | med |
| 5 | **Player club minutes / form / fatigue** | pre-match strength | FBref / mirror | post-matchday | med (scraping terms) | free data | yes | med | high | med |
| 6 | **Timestamped pre-match odds (dev folds)** | pre-match W/D/L | none pre-2020 (BLOCKED) | The Odds API (have) | low | credits | have | high | low | med (blocked pre-2020) |
| 7 | **Referee + discipline history** | red-card/cards | source TBD | pre-match appointment | med | unknown | TBD | low | med | low |
| 8 | **League suspension / competitive inactivity** | pre-match strength | derivable | derivable | low | free | n/a | med | med | low |
| 9 | **Travel / weather / altitude** | pre-match (small) | Open-Meteo archive | Open-Meteo | low | free | no | low | low | low |

## Top 5 (ordered)
1. **Event-level xG/shots feed** — the single biggest in-play enabler (M3 failed without it).
2. **Confirmed lineups/benches/injuries** — pre-match strength + in-play sub-impact.
3. **Multi-competition historical event volume** — 48 matches is far too few; need many tournaments/leagues.
4. **Substitutions with player IDs + positions** — to model sub impact (counts alone are inert).
5. **Player club minutes / fatigue** — orthogonal pre-match signal.

## Data requests (pending; none implemented)
- New: `data_requests/pending/tier4_event_xg_feed.yaml` (gap #1/#3/#4 consolidated).
- Existing/related: `statsbomb_open_data.yaml` (historical events/lineups/xG), `fbref_player_minutes.yaml`
  (gap #5), `live_2026_results_lineups_provider_comparison.yaml` (live lineups/events — API-Football Pro),
  `historical_odds_dev_folds.yaml` (gap #6, pre-2020 BLOCKED), `referee_history.yaml`, `open_meteo.yaml`.

No new provider integrated, no new domain scraped — requests only, per governance.
