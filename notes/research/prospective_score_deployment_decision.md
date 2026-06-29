# Prospective Score — Root-Cause Remediation Deployment Decision

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

## Root cause (confirmed)
The collector cycle (`scripts/windows/shadow_collector_cycle.py`) calls `live_2026_shadow.py score` every
5 minutes, but **nothing in the cycle refreshes results**. `score()` filters
`data/processed/results_2026_footballdata.csv` to `status==FINISHED`; that file was last fetched while
matchday-1/2 were the latest finals (FINISHED only through 2026-06-20), so the 06-24..06-28 predicted
matches stayed `TIMED` and the team-pair join produced zero scored rows (silent empty write, rc=0).

## Two possible fixes
1. **Independent durable harvester** (this program) — refreshes final results into its own scoring root
   and scores append-only, fully isolated from the live collector. **Implemented, tested, idempotent,
   integrity all_ok; it recovered the full scorecard (34 scored + 1 documented exclusion = 35/35).**
2. **Narrow collector score-adapter patch** — insert a bounded football-data results refresh immediately
   before `score()` in the collector cycle (a single result-refresh adapter; no change to odds capture,
   prediction freeze, scheduler cadence, or models).

## Decision: RETAIN the independent harvester as the official scoring path; DEFER the collector patch.

### Assessment against the 11 required conditions for an in-collector deployment
| # | Condition | Status |
|---|---|---|
| 1 | Root cause demonstrated | ✅ |
| 2 | Independent harvester proves correct scoring | ✅ |
| 3 | Patch modifies only a narrow score/result-refresh adapter | achievable |
| 4 | Does not alter frozen prediction files | achievable |
| 5 | Does not alter odds-fetching logic | achievable |
| 6 | Does not alter scheduler cadence | achievable |
| 7 | Backwards-compatible | achievable |
| 8 | Tested in the isolated worktree | partial (harvester yes; in-collector wiring not vetted live) |
| 9 | Atomic file swap | scripted (below) |
| 10 | Rollback copy + command exist | scripted (below) |
| 11 | Post-deploy smoke test (collector healthy; append-only; no Odds API; no trade path) | not yet run live |

Conditions 8 and 11 cannot be **fully** guaranteed without mutating a **currently healthy, actively
running** live collector (5-min cadence, 47/500 credits, last result 0). The independent durable harvester
already delivers the program's objective with zero risk to the live collector, so patching the live
collector is **not necessary** and is therefore deferred. The official scoring path is
`WorldCupProspectiveScoreHarvester` (Phase 8).

## If the collector patch is later desired
Use `scripts/deploy_prospective_score_adapter.ps1 -Execute` (dry-run by default). It backs up the target,
performs an atomic swap of a single result-refresh adapter, runs a smoke test, and auto-restores on any
failure. Revert with `scripts/rollback_prospective_score_adapter.ps1`. The collector's branch, commit, and
Task Scheduler configuration are never changed; odds collection is paused only for the atomic file swap.
