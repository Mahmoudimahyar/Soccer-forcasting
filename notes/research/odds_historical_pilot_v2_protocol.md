# Odds API Historical Pilot V2 — Protocol & PREDECLARATION (Phase 4)

research_only / DIAGNOSTIC ONLY / not_runtime_approved / not_trade_eligible / not_live_eligible. This file is
committed BEFORE any odds retrieval, so the fixture selection is provably independent of the odds.

## Hard constraints (enforced in scripts/odds_historical_pilot_v2.py)
- Total research budget: <= 30 Odds API credits (historical odds = 10 credits / region / market).
- Plan: 2 historical-odds snapshots (region=eu, market=h2h) = 20 credits; read usage headers after every call;
  stop before exceeding 30. Reserve the rest for the active collector; do NOT touch its odds budget ledger.
- Endpoints: ONLY `/v4/historical/sports/soccer_fifa_world_cup/odds` (+ optional events). No live polling loop.
- Snapshot timed >= 60 minutes before kickoff (morning-of-matchday snapshot precedes all that day's kickoffs).
- Require >= 3 bookmakers with all three 1X2 outcomes per fixture; no-vig per bookmaker; median across bookmakers.
- Mark all results diagnostic only; do NOT train / tune / promote / modify M1-M5.

## PREDECLARED fixtures (selected from PUBLIC knowledge of WC2022; BEFORE seeing any odds)
Selection satisfies: 2 favorites, 2 balanced, multiple matchdays, >= 1 realized draw.
| # | match | date (UTC) | kickoff (UTC) | matchday | declared expectation | realized result |
|---|---|---|---|---|---|---|
| 1 | Argentina vs Saudi Arabia | 2022-11-22 | 10:00 | MD1 | favorite (Argentina) | 1-2 (upset) |
| 2 | France vs Australia | 2022-11-22 | 16:00 | MD1 | favorite (France) | 4-1 |
| 3 | Denmark vs Tunisia | 2022-11-22 | 13:00 | MD1 | balanced | 0-0 DRAW |
| 4 | Mexico vs Poland | 2022-11-22 | 17:00 | MD1 | balanced | 0-0 DRAW |
| 5 | Brazil vs Serbia | 2022-11-24 | 19:00 | MD1 | favorite (Brazil) | 2-0 |
| 6 | Uruguay vs South Korea | 2022-11-24 | 13:00 | MD1 | balanced | 0-0 DRAW |

- Favorites: #1, #2, #5.  Balanced: #3, #4, #6.  Realized draws: #3, #4, #6 (>=1 required).  Matchdays: 11-22, 11-24.
- Snapshots: 2022-11-22T08:00:00Z (covers #1-#4, all >=60 min pre-KO) and 2022-11-24T08:00:00Z (covers #5-#6).
- If fewer than 4 fixtures meet the >=3-bookmaker / all-3-outcomes / >=60-min rule: classify the pilot
  **insufficient**, document the reason, do NOT relax the rules, and continue.
