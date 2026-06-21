# Tier-1 Data Card — World Cup Forecasting Foundation

Version: `tier1-2026-06-20`. Companion: `data/processed/source_provenance.json`,
`notes/research/provenance_policy.md`, `data/reference/tiebreak_rules_2026.yaml`.

## Canonical match table — `data/processed/research_modeling_table.csv`
- **Rows:** 369 played World Cup group-stage matches, **1998–2026**.
- **Per-year:** 48 each for 1998–2022 (jfjelstul) + 33 played 2026 (football-data: 24 MD1 + 9 MD2).
- **Grain:** one row = one regulation-time group match prediction opportunity.
- **Identity/labels:** match_id, kickoff_utc, tournament, stage='group', group (A–L), matchday (1/2/3),
  team_a/team_b (canonical), neutral/host context, confederation pair.
- **Result fields (stored, stripped before modeling):** goals_a, goals_b, outcome, is_draw.
- **Pre-match features (all time-safe):** elo_a/elo_b/elo_delta/abs_elo_delta; group state
  (points/gd/gf/played pre, prior_group_draws/goals/matches via strict-before); schedule-adjusted
  ppg/state deltas; venue host/neutral; confed_same; market placeholders + missingness; FIFA
  release-normalized deltas (joined as-of); low_block_risk; travel_fatigue.
- **Sibling:** `forecast_targets_2026.csv` (39 upcoming 2026 matches, no result).

## Canonical team-name mapping
`ingest.canonical_team_name` + `TEAM_ALIASES` + per-source EXTRA aliases (build_research_table,
fetch scripts). Reconciles martj42 / jfjelstul / football-data / odds / FIFA / Transfermarkt
spellings (e.g., "Czech Republic"→"Czechia", "South Korea"→"Korea Republic",
"Bosnia and Herzegovina"/"Bosnia-Herzegovina"→"Bosnia", "DR Congo"/"Democratic Republic of the Congo"→"Congo DR").

## Pre-match Elo timeline — `data/processed/elo_history.csv`
Walk-forward over 49,482 martj42 internationals (+ football-data freshest 2026 results).
`elo_before(team, date)` returns the Elo from the team's last match **strictly before** `date`
(K=40, scale=400, home-adv=65, GD multiplier) → no same-match leakage. Validated best on
selection folds (cycle 2a; importance-weighting rejected).

## Sources & provenance (9; content-hashed in source_provenance.json)
martj42 (CC0), jfjelstul (MIT), football-data.org (keyed), The Odds API live+historical (keyed),
Dato-Futbol FIFA (open), Transfermarkt/dcaribou (CC-BY-NC-SA), Wikipedia 2026 format (CC-BY-SA).
Source-priority + disagreement handling in `provenance_policy.md`.

## 2026 format & simulator
48 teams / 12 groups of 4 / 72 group matches / top-2 + 8 best thirds → 32 advance.
**Active engine: `simulation/official_standings.py`** — official 2026 Article-13 order
(head-to-head before overall GD, recursive; lots removed). Tests: `tests/test_official_tiebreak.py`
(two/three-team H2H, H2H-goals, conduct, 12-third ranking, exactly-8-advance, seed) +
`tests/test_simulation_2026.py` (legacy baseline). Legacy `group_simulator.py`/`standings.py`
retained as a baseline only. Correcting the order changed 2026 advancement materially (max
|Δp_advance| 0.107; e.g. Turkey 0.107→0.000) — see `tier_1_remediation.md`.

## Known limitations (carried into later tiers)
- **Tiebreak:** official H2H order now IMPLEMENTED in the active engine; `conduct`/`fifa_rank`
  act as separators only when supplied (default neutral); official FIFA PDF not yet archived.
- Secret hygiene: `.env.example` still holds real keys (operator must move to `.env`) — guarded by
  `tests/test_secret_hygiene.py` + `scripts/check_secret_hygiene.py`; see `security_remediation.md`.
- **No historical odds < 2020**; no free historical international xG/lineups; API-Football key is
  RapidAPI-type (rejected by the direct-host adapter).
- **Provenance envelope** is file-level (hash+URL) for historical CSVs; per-record hashing applies
  to new structured pulls — to be tightened when the live event pipeline (Tier 4) is built.

## Leakage controls (enforced by 21 leakage/quality/simulator tests)
elo_before strict-<; group keys scoped (year,group); strict-before group aggregates for
simultaneous final matchday (covered by an always-on unit test + the real-table invariant);
fixed evaluator strips forbidden post-match columns by name and dtype.
