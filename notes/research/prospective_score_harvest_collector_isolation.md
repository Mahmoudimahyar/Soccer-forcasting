# Prospective Score Harvest — Collector & Active-Worker Isolation Record

Captured 2026-06-29 (system date) before any write. Read-only reconnaissance.
**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

## WorldCupShadowCollector (the active prospective collector) — DO NOT TOUCH
- **State:** Ready · **LastRun:** 2026-06-29 19:03 (local) · **NextRun:** 2026-06-29 19:08 · **LastResult:** 0 (healthy)
- **Trigger:** every 5 minutes (PT5M)
- **Action:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Mahyar\worldcup_draw_model_lab_FINAL\scripts\windows\run_shadow_collector.ps1"`
- **WorkingDirectory:** `C:\Users\Mahyar\worldcup_draw_model_lab_FINAL` (the **main checkout**, NOT a worktree) ✓
- **Active branch / commit:** `v1-5-prospective-operations` @ `dc73318` (== this harvest worktree's base commit) ✓
- **Heartbeat:** `outputs/live_shadow/collector_heartbeat.json` (status `ok`, ts 2026-06-29T22:43Z)
- **State:** `outputs/live_shadow/collector_state.json`
- **Odds budget:** `outputs/live_shadow/odds_budget.json` — 47 / 500 credits used (453 remaining)
- **Hard end:** cycle self-stops past 2026-07-05T00:00Z; task repeats until ~2026-07-04 20:00Z
- **Frozen prediction ledger:** `outputs/research/live_2026_shadow_predictions.csv` (680 data rows at audit)
- **Prediction queue:** `data/reference/future_2026_prospective_queue.csv` (72 rows: 28 eligible, 44 skipped)
- **Current score outputs:** `outputs/research/live_2026_shadow_metrics.csv`, `..._calibration.csv`, `prospective_scorecard.csv` — **all EMPTY**
- **Current scoring-status distribution:** every queue row `scoring_status=pending`; 0 scored

**Verification:** collector points to the main checkout (not this worktree); paper flags `KALSHI_ENABLE_LIVE_TRADING=false` / `TRADING_MODE=paper`; no trade/order path reachable from the collector or this program. This program will not switch the collector branch, alter its Task Scheduler config, modify odds-collection logic, or change prediction-freeze logic.

## Active concurrent research worker — DO NOT TOUCH
- **WorldCupHierarchicalDomainTransferRun:** State Ready, LastRun 2026-06-29 19:00, LastResult 0.
  - Action: `...\worldcup-hierarchical-transfer\scripts\run_hierarchical_domain_transfer_v1.ps1`
  - WorkingDirectory / worktree: `C:\Users\Mahyar\worldcup-hierarchical-transfer` (branch `hierarchical-domain-transfer-v1` @ `52d4362`)
- **WorldCupHierarchicalTransferGatekeeper:** Ready, runs every 15 min (PT15M), gatekeeper script under `worldcup-evidence-power-consolidation`.
- It was NOT Running at audit (periodic-trigger task, between fires). Regardless: this program will not stop it, will not modify its worktree/datasets/models/registries/outputs, and will not consume its outputs as input.

## This program's isolation guarantees
- Runs entirely in its **own worktree** `C:\Users\Mahyar\worldcup-prospective-score-harvest` (`prospective-score-harvest-v1`).
- **Reads** immutable collector artifacts from the main checkout by absolute path (predictions / queue / forecast targets / raw odds snapshots are gitignored, so they are not in this worktree).
- **Writes** only to its own scoring root `outputs/live_shadow/scoring_v1/` (worktree-relative) and its own `notes/`, `schemas/`, `scripts/`, `data/reference/`, `tests/`.
- Refreshes **final results only** via football-data.org (key `FOOTBALL_DATA_KEY`, SET) / API-Football Pro fallback — **never** The Odds API; never fetches odds; never retrains; never touches frozen predictions or the collector's `results_2026_footballdata.csv`.
