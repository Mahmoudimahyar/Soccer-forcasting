# Five-Hour Session — Report

**Status: IN PROGRESS (launch + interim).** The bounded supervisor runs autonomously to the deadline
and self-writes `session_summary.json`; this file holds the launch state + interim results + the exact
finalize procedure. Final metrics populate as the two in-window matches complete.

- session start: 2026-06-21T18:24:02Z · planned end: 2026-06-21T23:24:02Z
- supervisor: `scripts/five_hour_supervisor.py` (background) · session dir:
  `outputs/live_shadow/session_20260621T182402Z/`
- tests at launch: **pytest 131 passed**
- governance: no live trading; `KALSHI_ENABLE_LIVE_TRADING=false`; B1 sole approved model; M2–M5
  shadow; candidate.py untouched; no protected/`.env` edits; canonical Elo not mutated (session-scoped).

## What was built/launched
1. **Bounded 5h live-shadow supervisor** — own timed loop; ≤30 Odds credits/session; ≥10 min between
   odds requests (1 batch covers all events); ≥10 min football-data polls requiring **FINISHED**
   status; idempotent session-scoped Elo ledger + transaction log; restart-safe state file;
   fail-closed with bounded backoff; clean stop + `session_summary.json`. Dry-run validated before launch.
2. **Snapshot freezer** — immutable M1–M5 predictions with snapshot_type (baseline/T-90/T-15/final),
   full envelope (SE/CI/entropy/risk band/data_completeness/market/n_books/overround).
3. **Integrity validators** (`shadow_integrity.py` + 6 tests + `validate_shadow_integrity.py`) — live
   file passes ALL: no duplicate snapshots, all pre-kickoff, probs sum to 1, no-vig sums to 1,
   frozen blend weights.
4. **2022 replay quality** (`replay_quality_2022.py` + `2022_replay_quality.md`).

## Interim metrics (T+~0:10; update at finalize)
- credits: **1 / 30** · snapshots: **34 baseline** across 34 matches · fixtures recorded: **37** (idempotent)
- shadow models scored: **0** so far (in-window finals not yet played) — **UNDERPOWERED, do not interpret**
- in-window matches: Belgium–Iran (KO 19:00Z, expect final ~20:50Z → scorable in-window),
  Uruguay–Cape Verde (KO 22:00Z, final ~23:50Z → likely just after window)
- provider health: Odds API + football-data both responding; no failures yet

## Data-quality observations
- 2022 events: 48/48 matches, 744 events, 0 missing minutes; goal reconciliation 47/48 (1 own-goal/VAR
  edge); replay goals monotonic (no future leak). Red cards low-N (2); xG absent; lineups not bulk-cached.
- Live shadow predictions pass all integrity invariants.

## Data requests created (this + prior sessions, awaiting your action)
- `historical_odds_dev_folds.yaml` (no clean pre-2020 WC odds exist → market promotion blocked).
- `live_2026_results_lineups_provider_comparison.yaml` (preferred: API-Football Pro ~$25-30/mo).
- `statsbomb_open_data.yaml`, `fbref_player_minutes.yaml`, `referee_history.yaml`, `open_meteo.yaml`.

## Exact next recommended task
Let the supervisor complete; at the deadline run the finalize procedure below to score Belgium–Iran
(and any other final), then read `session_summary.json`. The standing highest-value item remains
**prospective live-2026 M1–M5 scoring accumulation** (this session starts it).

## Finalize procedure (run at/after 23:24Z, or when the supervisor process has exited)
```bash
cd /c/Users/Mahyar/worldcup_draw_model_lab_FINAL
python -m pytest -q
python scripts/live_2026_shadow.py score          # score any finished predicted matches
python scripts/validate_shadow_integrity.py       # re-verify integrity
cat outputs/live_shadow/session_20260621T182402Z/session_summary.json
# then append final numbers (credits, snapshots-by-type, finalized, M1-M5 metrics) to this report
```

## Exact command to run the NEXT five-hour session
```bash
python scripts/five_hour_supervisor.py --hours 5 --max-credits 30      # background; self-finalizes
```

## Pre-trading conditions (unchanged; none met)
A promoted+approved model (frozen-protocol evidence), registry update + human sign-off, registry-bound
risk gate pass, `KALSHI_ENABLE_LIVE_TRADING=false` (paper only), reviewed market mapping. Until then:
shadow only, no trading.
