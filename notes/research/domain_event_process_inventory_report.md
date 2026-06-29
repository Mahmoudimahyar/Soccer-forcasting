# Domain Event-Process Inventory Report (Phase 1)

_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_

Generated: 2026-06-28T19:03:22Z

## Scope

Inventory of event-process completeness across the two domains of the hierarchical cross-domain transfer study. INTERNATIONAL is the PRIMARY (and only) test population; CLUB is AUXILIARY training only and is never used as an international test row.

## Domain summaries

### International (persistent event lake)

- lake root: `C:\Users\Mahyar\worldcup_data_lake\statsbomb_open\international_event_lake_v1`
- objects indexed: **258**
- objects read through the engine (REAL completeness): **258**
- objects absent/unreadable: 0

Per-competition (international):

| competition | matches | regulation-eligible | xG verified | possession | pressure | snapshots |
|---|---:|---:|---:|---:|---:|---:|
| Copa America 2024 2024 | 28 | 28 | 28 | 28 | 28 | 3452 |
| FIFA World Cup 2018 2018 | 64 | 64 | 64 | 64 | 64 | 8269 |
| FIFA World Cup 2022 2022 | 64 | 64 | 64 | 64 | 64 | 7614 |
| UEFA Euro 2020 2020 | 51 | 51 | 51 | 51 | 51 | 6412 |
| UEFA Euro 2024 2024 | 51 | 51 | 51 | 51 | 51 | 6612 |

### Club (event-process auxiliary corpus)

- fixtures declared in aux manifest: **669**
- club event objects materialized in this worktree: **669**
- note: 669/669 club event objects materialized

Per-competition (club, manifest-level):

| competition | matches | seasons | event objects present |
|---|---:|---:|---:|
| La Liga | 150 | 18 | 150 |
| Ligue 1 | 138 | 3 | 138 |
| Premier League | 118 | 2 | 118 |
| Serie A | 81 | 2 | 81 |
| Indian Super league | 80 | 1 | 80 |
| 1. Bundesliga | 68 | 2 | 68 |
| Champions League | 18 | 18 | 18 |
| Major League Soccer | 6 | 1 | 6 |
| Copa del Rey | 3 | 3 | 3 |
| UEFA Europa League | 3 | 1 | 3 |
| Liga Profesional | 2 | 2 | 2 |
| FIFA U20 World Cup | 1 | 1 | 1 |
| North American League | 1 | 1 | 1 |

## Quality-grade distribution

| grade | international | club | meaning |
|---|---:|---:|---|
| A | 258 | 669 | full clock + XI + verified xG + rich stream + snapshots |
| B | 0 | 0 | full clock + XI, partial xG or thinner stream |
| C | 0 | 0 | usable but missing clock/XI or very thin |
| D | 0 | 0 | event-level completeness not derivable here (raw absent) |

## Stable-completeness headline (international)

- matches with verified xG coverage: 258/258
- matches with possession structure: 258/258
- matches with pressure events: 258/258
- matches with set-piece deliveries: 258/258
- matches regulation-eligible: 258/258

## Honesty / leakage notes

- International completeness is computed from the REAL lake event objects through the canonical snapshot engine (no imputation; absent fields flagged, never zeroed).
- The club raw corpus is not materialized in this worktree; its event-level completeness is honestly flagged `raw_absent`. This is recorded so Phase 2 can declare cross-domain feature overlap `data_insufficient` rather than fabricate club distributions.
- Club rows carry `target_eligible_wdl=False` and are never international test rows.
