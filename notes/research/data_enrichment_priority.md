# Data Enrichment Priority Roadmap — Data Enrichment Gate 1 (2026-06-21)

Ranked data-value report for improving the approved **B1/Elo** model and enabling Tier 3–5. This is
analysis + ingestion contracts only — **no provider was expanded, no domain scraped, no model
changed.** Sources are ordered by the mandated priority (1 = highest) unless evidence dictates
otherwise; here the evidence supports the default order.

## Ranked candidates (economics + risk)
| # | source / field group | expected incremental value | historical avail | live avail | point-in-time usable | account | cost | legal/terms risk | rate-limit risk | leakage risk | impl. difficulty | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Timestamped pre-match + in-play odds** (The Odds API, N/O) | **High** (market is the strongest single signal; only validatable proxy that beats Elo on 2022) | from 2020-06 only | yes | yes (snapshot ≤ kickoff / ≤ decision) | yes (have key) | ~20k/mo tier | low | medium (quota) | high if snapshot mis-timed | low (adapter exists) | **approved** |
| 2 | **Confirmed lineups, benches, injuries, suspensions** (API-Football / official, B/Q) | High (XI quality + key absences move strength materially) | paid tiers | yes | yes (after official release) | yes — **key broken** | direct free 100/day or RapidAPI | low | medium | high (must gate to release time) | med (blocked on key) | **blocked** |
| 3 | **Event timelines: goals, cards, subs, shots, penalties** (API-Football / licensed, C–K) | High for in-play; Med for pre-match | paid tiers | yes | yes (event time ≤ decision) | yes — **key broken** | as above | low | medium | high (in-play look-ahead) | med | **blocked** |
| 4 | **Historical event-level WC data** (StatsBomb open data) | Med-High (offline xG / in-play model training before any live feed) | selected tournaments | n/a | historical only | no | free (non-commercial) | **med (NC license)** | low | low (other-match only) | med | needs sign-off |
| 5 | **Player club minutes, form, fatigue, role** (FBref / mirror) | Med (squad-strength adjustment; player-state) | multi-season | post-matchday | yes (club data ≤ cutoff) | yes | free data, access restricted | **med-high (scraping terms)** | high | med (post-cutoff form) | high | needs approved method |
| 6 | **Tactical / formation data** (API-Football lineups / StatsBomb) | Low-Med | paid / open | yes | yes | partial | — | low-med | medium | med | med | via #2/#4 |
| 7 | **Weather, travel, altitude, humidity, heat** (Open-Meteo, P) | Low (small, situational) | yes (archive) | forecast | yes (forecast issued ≤ decision) | no (keyless) | free | low | low | low | low (adapter exists) | draft (recommend approve) |
| 8 | **Referee + discipline history** | Low (noisy, low-N) | source-dependent | pre-match appointment | yes | TBD | unknown | med (source TBD) | unknown | low | med | draft (source TBD) |
| 9 | **League disruption / competitive inactivity** | Low-Med (derivable from #5) | derived | derived | yes | n/a | n/a | low | low | med | med (derived feature) | derived from #5 |

## Which prediction targets each source helps
| # | source | pre-match W/D/L | expected goals | advancement sim | in-play W/D/L | next-goal | red-card | sub impact | player-state |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | odds | ✅ | ➖ | ✅ (via probs) | ✅ | ➖ | ➖ | ➖ | ➖ |
| 2 | lineups/injuries | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | ✅ |
| 3 | event timelines | ➖ | ✅ | ➖ | ✅ | ✅ | ✅ | ✅ | ➖ |
| 4 | historical events | ➖ | ✅ (train) | ➖ | ✅ (train) | ✅ (train) | ✅ (train) | ✅ (train) | ➖ |
| 5 | player minutes/form | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | ✅ | ✅ |
| 6 | tactical/formation | ➖ | ✅ | ➖ | ✅ | ✅ | ➖ | ✅ | ➖ |
| 7 | weather | ✅ (small) | ✅ (small) | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| 8 | referee | ✅ (small) | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ |
| 9 | league disruption | ✅ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ✅ |

## Data requests (pending)
- Approved + integrated: `the_odds_api`, `football_data_org`, `fifa_world_ranking_history`.
- **Blocked:** `api_football` (key rejected by both direct and RapidAPI — see source readiness audit).
- **New this gate:** `open_meteo` (keyless, recommend approve), `statsbomb_open_data` (free historical
  events, license sign-off), `fbref_player_minutes` (needs a terms-compliant access method),
  `referee_history` (source TBD). Files under `data_requests/pending/`.

## Exact next highest-value implementation task
**Build the historical pre-match odds backfill for B1 evaluation** — i.e., ingest timestamped
pre-match odds (The Odds API historical, 2020-06→) into schema N via the append-only raw store, then
run a paired-bootstrap of a market-anchored model vs B1 on the **temporal folds where odds exist**
(2022 gate + post-2020 internationals). This is the single test that could justify promoting a
market model over B1 — it uses an already-approved source, needs no new account, and respects the
known pre-2020 odds gap. (Requires your approval to begin ingestion; not started here.)

Runner-up: unblock #2 (a working API-Football key) to bring confirmed lineups/injuries online for
pre-match strength adjustment.
