# xG Event-State Features — Data Card (Phase 3, xG bridge)

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Artifact: `data/processed/xg_event_state_features_v1.csv` (gitignored — derived only)
Builder: `scripts/build_xg_event_state_features.py` · version `xg_event_state_v1`
Source: StatsBomb Open Data events for **exact-bridged** international games
(`api_statsbomb_match_bridge_v1`). StatsBomb Open Data license — non-commercial research, attribution.

## What this is

Leakage-safe, in-play xG **state** features for senior men's international games that are EXACT-matched
between API-Football and StatsBomb open data. One row per `(bridged match, decision_minute)` on the
regulation grid `10..90` step 5 (17 decision minutes). Built only for the 258-game bridge; this bounded
run covers **58 games** (986 rows) — see the bridge quality report.

## Causal contract (enforced + tested)

- **No look-ahead.** A feature at decision minute `t` uses ONLY events with continuous match-clock minute
  `<= t` (`_events_up_to`). No future shot, xG, or goal enters the state at `t`. Covered by
  `tests/test_statsbomb_bridge.py::test_no_future_xg_leaks_into_state`.
- **Timestamps are match-clock, not publication time.** StatsBomb `minute`/`second` are in-match elapsed
  time. They are NEVER interpreted as a live wall-clock / publication / decision time. (This dataset
  models "given the match state at elapsed minute t", not "given what a live feed had published by t".)
- **Regulation only.** Events in periods > 2 (extra time / shootout) are excluded from the grid and
  flagged via `extra_time_events_present`. Shootouts never enter in-play state.
- **Own-goal semantics.** "Own Goal For" credits the beneficiary side in the score view and carries **no
  xG** (no shot model). Normal goals are shots with outcome `Goal`.
- **Determinism.** Pure function of the event JSON; identical inputs → identical rows
  (`test_features_deterministic`).

## Columns

| Column | Meaning |
|---|---|
| `bridge_id`, `api_fixture_id`, `sb_match_id` | identity (links to the exact bridge) |
| `competition_label`, `comp_type` | competition; `comp_type=international` (club kept separate elsewhere) |
| `kickoff_date`, `decision_minute` | agreed UTC date; decision minute t (10..90 step 5) |
| `home`, `away` | API-Football team names (bridge orientation) |
| `cum_xg_home`, `cum_xg_away`, `cum_xg_diff` | cumulative StatsBomb xG for each side / difference, up to t |
| `roll5_xg_diff`, `roll10_xg_diff` | xG difference accumulated in `(t-5, t]` and `(t-10, t]` |
| `shot_count_home`, `shot_count_away`, `shot_count_diff` | shot counts up to t / difference |
| `time_since_last_shot` | minutes since the most recent shot by either team (cap 95) |
| `time_since_last_major_chance` | minutes since the most recent shot with `statsbomb_xg >= 0.30` (cap 95) |
| `last_event_index` | StatsBomb `index` of the last event used at t (event-order completeness) |
| `score_home_to_t`, `score_away_to_t`, `score_diff_to_t` | goals up to t (incl. own-goal beneficiary) |
| `n_shots_total_regulation` | total regulation shots in the match (completeness) |
| `has_any_shot_event` | flag: at least one regulation shot parsed |
| `extra_time_events_present` | flag: ET/shootout events existed (excluded from grid) |
| `sb_events_sha256` | sha256 of the source StatsBomb events JSON (provenance) |
| `feature_builder_version` | `xg_event_state_v1` |

## Parameters

- Decision grid: `range(10, 91, 5)` (regulation).
- Major-chance xG threshold: `MAJOR_CHANCE_XG = 0.30`.
- Time-since caps: `CAP_SINCE = 95.0` minutes when no qualifying prior event exists.

## Known limitations / honesty

- **Small sample.** 258 bridged international games (58 feature-built here) is a low-powered fusion set;
  validate any xG-fusion model with leave-one-competition-out and do not promote on this evidence alone
  (per the frozen preregistration).
- **Bounded acquisition.** Only 12 event JSONs/competition were downloaded this run. Full feature coverage
  for all 258 bridged games: re-run `acquire_statsbomb_open.py --events-per-comp -1` then rebuild.
- **xG is StatsBomb's model output**, not ground truth; treat as a strong but noisy chance-quality proxy.
- **No player-level fusion here.** This card covers team-level in-play xG state. Player-ID linkage (exact
  API-Football integer `player.id`) lives in the separate player-history plane and is not mixed in.

## Reproduce

```bash
python scripts/acquire_statsbomb_open.py --events-per-comp 12
python scripts/build_api_statsbomb_match_bridge.py
python scripts/build_xg_event_state_features.py
python -m pytest tests/test_statsbomb_bridge.py -q
```
