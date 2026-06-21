# Tier 2 — Data Readiness Gate

All numbers measured from `data/processed/research_modeling_table.csv` (+ market/FIFA files).
Reproduce: `scripts/build_research_table.py`; proofs re-run inline (see commands at bottom).

## Match counts (played WC group-stage)
| Year | Matches | Notes |
|---|---|---|
| 1998 | 48 | 32-team era (8 groups × 6) |
| 2002 | 48 | |
| 2006 | 48 | |
| 2010 | 48 | **dev fold** |
| 2014 | 48 | **dev fold** |
| 2018 | 48 | **dev fold** |
| 2022 | 48 | **release gate** |
| 2026 | 33 | **24 MD1 (locked transfer) + 9 MD2 played** |
| **Total played** | **369** | stage = group only |
- **2026 completed Matchday 1:** 24 matches. **Remaining 2026 group matches:** 39 (15 MD2 + 24 MD3).
- All rows: `stage == "group"`; group keys scoped per tournament (`group_uid = year_letter`).

## Candidate-feature missingness (% NaN in the 369 played rows)
| Feature | Missing | Source & availability rule |
|---|---|---|
| elo_a, elo_b, elo_delta, abs_elo_delta | 0.0% | internal Elo from martj42 internationals; `elo_before(strict < kickoff)` |
| matchday | 0.0% | jfjelstul (≤2022) / football-data (2026) |
| prior_group_draws, prior_group_goals_per_match, prior_group_matches | 0.0% | computed from **earlier** group matches only (strict-before) |
| group_state_points_delta, group_state_gd_delta, points/gd_*_pre | 0.0% | pre-match standings from completed earlier matchdays |
| venue_host_advantage, venue_neutral | 0.0% | static host map by year (pre-tournament) |
| confed_same, confed_intercontinental | 0.0% | static confederation table (pre-tournament) |
| fifa_z_delta, fifa_rank_pct_delta, fifa_age_days | 0.0% | Dato-Futbol FIFA ranking, asof `release_date <= kickoff` |
| travel_fatigue | 0.0% | proxy (defaults; no real rest/travel inputs) |
| **p_a_market, p_draw_market, p_b_market, market_total_goals** | **100.0%** | **no odds in the WC table** (`market_is_missing=1` for all 369) |
| **low_block_risk** | **100.0%** | depends on `market_total_goals` → unavailable (do not impute) |

## Leakage proofs (re-run, real numbers)
- **Elo is pre-match & excludes the predicted match:** `elo_before` uses `bisect_left(dates, kickoff)`
  and returns the team's Elo *after its last match strictly before kickoff* → the match itself is
  never folded in. Walk-forward over date-sorted history. (Unit-tested.)
- **Group-state uses only completed earlier matches:** `played_a_pre ≤ matchday-1` (all rows: True);
  `points_a_pre ≤ 3·played_a_pre` (True); MD1 rows have `points_a_pre == 0` (True).
- **Simultaneous final-matchday no leak:** `max(prior_group_matches) = 4`; every MD3 row has
  `prior_group_matches == 4` (never 5) → the two simultaneous MD3 games do not see each other.
- **FIFA publication-date aligned:** `fifa_age_days` min = **7** (every release precedes its kickoff);
  median age 15–51 days for 1998–2022, **635 days for 2026** (dataset ends 2024-09 → stale-but-time-safe,
  flagged `fifa_is_stale`).
- **2022 odds pre-kickoff:** all 48 rows have `snapshot_time < commence_time` (median lead 94.4 min;
  min 94.4 min) → T-90 pre-kickoff, no post-kickoff odds.

## Odds / market status (critical for B6/B7)
| Fold | Odds available? | File |
|---|---|---|
| 2010, 2014, 2018 dev | **NO** (Odds API history starts 2020-06) | — |
| 2022 gate | **YES** (48, T-90 no-vig consensus) | `data/processed/market_features_2022.csv` |
| 2026 MD1 locked | live snapshot only (not historical) | `data/processed/market_features_2026.csv` |
- **Existing odds quality:** 2022 = real, timestamped, pre-kickoff (no-vig consensus across 32–35
  books). The seed `data/seed/sample_odds_2026.csv` is **synthetic placeholder** (book
  `seed_demo_not_real_odds`) — **never used** in any metric; the WC table market columns are all NaN.
- **No untimestamped or post-kickoff odds are used anywhere.**

## Player / lineup / xG / event data
- **None that is historical and time-safe** for the WC folds. Transfermarkt lineups cover only
  Copa/AFCON/AsianCup (not WC/Euro); no free historical international xG; API-Football key is the
  RapidAPI type (rejected by the adapter). → in-play/player features are **out of scope for Tier 2**.

## Features that are UNAVAILABLE — must NOT be imputed with invented values
- Market probabilities & totals for 2010/2014/2018 (and as backtest history generally).
- `low_block_risk` (market-derived) for all WC folds.
- Real rest/travel/fatigue, lineups, xG, injuries (only proxies/defaults exist).
These are represented by explicit missingness (NaN + `market_is_missing` flag), never faked.

## Tier-2 rules adopted (per instruction)
- **Market comparison:** B6 is evaluated **only on folds with real timestamped odds (2022)** and is
  compared to other models **on the same 2022 subset only** — never across different match sets.
  For dev folds (2010/14/18) B6 is **marked unavailable**.
- **B7 has two variants:** `B7_nomarket` (Elo + scoreline + tournament-state, all folds) and
  `B7_market` (adds no-vig market; **2022 only**). Missing market handled via missingness indicator,
  no fake odds.
- **Calibration:** fit calibrators on **train-fold data only** (never the test fold); no isotonic on
  tiny folds unless it improves held-out calibration without extreme probabilities (it did not — the
  earlier isotonic B7 was discarded). Report calibration slope/intercept + reliability.

## Verdict
Data is **ready** for a rigorous Tier-2 baseline pass on calibration-quality metrics, with B6/market
restricted to the 2022 gate and dev-fold selection kept market-free. The binding data gap is the
absence of pre-2020 odds (B6 cannot be validated on dev folds).

```
# proofs reproduced via:
python -c "import pandas as pd; t=pd.read_csv('data/processed/research_modeling_table.csv', parse_dates=['kickoff_utc']); ..."  # see git history of this report
```
