# V1.5 Prospective Readiness — Completion Report (2026-06-23)

Branch `v1-5-prospective-operations`. All work is research_only; **B1 remains the sole approved runtime
pre-match model; trading stays paper/disabled.**

## Exact readiness level
**OPERATIONALLY READY (dry-run verified) for prospective pre-match capture; in-play capture ready
pending the user's activation of a verified live source.** No model claim is made or due yet.

## Current clean prospective pool
**28 eligible not-started 2026 WC matches** (`data/reference/future_2026_prospective_queue.csv`), each
with a precomputed Elo anchor. 44 fixtures excluded (43 finished + 1 in-progress) as
`completed_not_clean_prospective`. Earliest eligible kickoff 2026-06-23T17:00Z. Knockout fixtures will
add more once their teams are determined.

## Direct API-Football status
**Compatible** (paid Pro plan): auth accepted; 2026 fixtures/standings/events/subs/cards/lineups all
2xx; rate-limit headers present. Read-only adapter built (`operations/api_football_adapter.py`) — key
never logged; quota-aware; raw payloads append-only + gitignored.

## Collector status
**Built and tested (200 tests pass).** Immutable first-write-wins ledger; frozen-M2 predictor with a
leakage guard (`event_source_timestamp <= decision_timestamp`); post-match scorer (metrics only);
session integrity (heartbeat, manifest, quota, staleness, fail-closed reconciliation,
MISSED_UNRECOVERABLE, clean shutdown, resume). **Safe by default = dry-run.** Dry-run confirmed: no
request before a window's scheduled time; deterministic pre-match capture; nothing written in dry-run.

## Scheduler status
**Materials prepared, NOT installed and NOT activated.** Windows Task Scheduler + cron runners and
installers (`scripts/run_prospective_collection.{ps1,sh}`, `install/uninstall_windows_task_scheduler.ps1`)
+ setup docs + ops checklist. Bounded single-pass runs (no daemon); graceful no-op when nothing is due.

## Data-provider recommendation
**Sportmonks** (lowest-cost, self-serve: base + xG add-on + historical-archive one-time) as the path
that can plausibly meet the 500/500 thresholds; **escalate to StatsBomb commercial/academic** if
per-shot xG depth is insufficient for the next-goal model. Opta only if enterprise coverage/latency is
required. The 150-red threshold likely needs club pooling regardless. See
`data_provider_decision_package.md` + `data_requests/pending/provider_comparison.yaml`.

## External actions needed from you
1. **(Optional, to capture)** decide to activate the collector and install the scheduler (manual).
2. **(Optional, to capture in-play)** confirm a verified live event source.
3. **(To unblock player/next-goal/card models)** approve + subscribe to a data provider (recommended:
   Sportmonks) — a **paid action**.
Everything else in this sprint is complete and needs nothing from you.

## Exact command to activate the prospective collector
Review first (writes nothing):
```
python scripts/prospective_collect.py
```
Activate real capture (records frozen pre-match predictions for due windows, first-write-wins):
```
EXECUTE=1 python scripts/prospective_collect.py --execute        # one bounded pass
```
Or schedule it (Windows): `./scripts/install_windows_task_scheduler.ps1 -IntervalMinutes 15` then set
`EXECUTE=1` in the task env; (cron): see `docs/CRON_SETUP.md`.

## What happens automatically after activation
Each scheduled run: captures any **due** pre-match window (T-90/T-15) deterministically from the Elo
anchor (no API call), and — if `--execute` + a verified live source — any due in-play checkpoint via the
read-only adapter; writes first-write-wins to the immutable ledger; updates heartbeat + session
manifest; marks missed windows; scores any FINISHED match (metrics only). It never trades, never changes
the frozen model, never promotes research output. Re-runs are idempotent and resume cleanly.

## Which results MAY be claimed
- After matches finish: prospective RPS / log-loss / draw-Brier of **frozen M2 vs the Elo anchor** on the
  28+ clean future matches — a genuine out-of-sample evaluation (point-in-time, never selected on 2026).
- Operational facts: collector ran, predictions captured before kickoff, integrity checks passed.

## Which results MAY NOT be claimed
- Any "improvement" of M2 from 2026 (the model is frozen; 2026 is scoring-only).
- The 41 already-finished 2026 matches as out-of-sample (they were seen → exploratory).
- Player/next-goal/card model performance (those classes remain data-blocked until a provider is added).
- Anything implying runtime/paper/Kalshi use of the research model.

## Why trading remains disabled
`KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`. The prospective model M2 is research_only and
not_runtime_approved; B1 is the sole approved model; no experimental output is wired to runtime, paper,
risk, or Kalshi (verified: runtime/trading do not import the operations plane). This sprint added
observation/scoring machinery only — it cannot place or influence any order.

## Verification (Phase 6)
- `pytest -q` = **200 passed**. Working tree clean (only an untracked local log).
- `git diff approved-b1-runtime..HEAD` over protected paths = **unchanged**.
- No `.env`, secret value, or raw provider payload tracked; large outputs gitignored; the only tracked
  `x-apisports-key` strings are header-NAME construction reading from `os.getenv` (no value).
- Future-2026 predictions are versioned (`m2_frozen@v2`) and point-in-time safe; completed matches
  excluded from the clean pool; scheduler safe-by-default and disabled until manually installed.
