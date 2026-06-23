# Active Collector Isolation Manifest (Offline Hardening Sprint, 2026-06-23)

Proof that the offline-hardening sprint is isolated from the **live** `WorldCupShadowCollector`.

## Active collector (DO NOT TOUCH)
- repository path: `C:\Users\Mahyar\worldcup_draw_model_lab_FINAL`
- active git branch: `v1-5-prospective-operations`
- active git commit: `dc733186fa37a2d5f8525c3b0dca55a58e9a9aae` (`dc73318`)
- scheduler task: `WorldCupShadowCollector` — State: Ready
  - action.execute: `powershell.exe`
  - action.arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\Users\Mahyar\worldcup_draw_model_lab_FINAL\scripts\windows\run_shadow_collector.ps1"`
  - action.workingDirectory: `C:\Users\Mahyar\worldcup_draw_model_lab_FINAL`
- heartbeat: `C:\Users\Mahyar\worldcup_draw_model_lab_FINAL\outputs\live_shadow\collector_heartbeat.json`
  (observed updating, ts 2026-06-23T05:03:12Z → collector is live)
- state: `...\outputs\live_shadow\collector_state.json`
- budget: `...\outputs\live_shadow\odds_budget.json`

## Offline-hardening worktree (ALL new work happens here)
- worktree path: `C:\Users\Mahyar\worldcup-offline-hardening`
- branch: `shadow-offline-hardening-v1` (based on `dc73318`)
- `git worktree list`:
  - `...\worldcup_draw_model_lab_FINAL  dc73318 [v1-5-prospective-operations]`  ← active collector
  - `...\worldcup-offline-hardening     dc73318 [shadow-offline-hardening-v1]`  ← this sprint

## Isolation proof
- The scheduled task's `action.workingDirectory` and `-File` path both point to the **main** checkout
  (`worldcup_draw_model_lab_FINAL`), **not** the worktree (`worldcup-offline-hardening`). The collector
  runs the main checkout's scripts and reads/writes the main checkout's `outputs/live_shadow/`.
- The main checkout remains on `v1-5-prospective-operations`; this sprint commits only to
  `shadow-offline-hardening-v1` in a separate working directory. `git worktree` does not modify the
  main working tree's files or HEAD.
- Therefore: no file the collector uses is touched, no branch switch occurs in the active checkout, the
  task is unmodified, cadence/budget/M1–M5 logic/frozen predictions are unchanged.

## Guarantees for this sprint
- No edits to the active checkout; no `git switch` there; no task install/uninstall/modify.
- KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper unchanged. `.env`/`.env.example`/candidate.py/
  runtime/trading/risk/Kalshi untouched. All new work: research_only / not_runtime_approved /
  not_trade_eligible.
