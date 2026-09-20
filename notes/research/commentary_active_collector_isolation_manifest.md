# Commentary Sprint — Active Collector Isolation Manifest (2026-06-23)

Proof that the Commentary Intelligence Research V1 sprint is isolated from the live
`WorldCupShadowCollector`.

## Active collector (DO NOT TOUCH)
- repository path: `C:\Users\Mahyar\worldcup_draw_model_lab_FINAL`
- active branch: `v1-5-prospective-operations`
- active commit: `dc73318`
- scheduler task: `WorldCupShadowCollector` — State **Ready**, workingDirectory =
  `C:\Users\Mahyar\worldcup_draw_model_lab_FINAL` (the MAIN checkout, not this worktree)
- heartbeat: `...\outputs\live_shadow\collector_heartbeat.json` (observed live, ts 2026-06-23T05:58Z)
- collector state: `...\outputs\live_shadow\collector_state.json`
- paper/trading flags: `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper` (unchanged)

## Commentary worktree (ALL new work here)
- path: `C:\Users\Mahyar\worldcup-commentary-intelligence`
- branch: `commentary-intelligence-research-v1` (based on `dc73318`)

## Isolation proof
- The scheduled task's workingDirectory points to the MAIN checkout, never this worktree → the collector
  runs main-checkout code and reads/writes main `outputs/live_shadow/`.
- The main checkout stays on `v1-5-prospective-operations`; this sprint commits only to
  `commentary-intelligence-research-v1` in a separate working directory. `git worktree` does not modify
  the main working tree's files or HEAD.

## Guarantees
No edits to the active checkout, no branch switch there, no task change, no odds budget / M1–M5 shadow /
frozen-prediction / frozen-in-play-M2 / B1 / candidate.py / approved_models / risk / trading / Kalshi /
.env change, no new odds/API-Football calls outside the running collector. All commentary work is
research_only / experimental / not_runtime_approved / not_trade_eligible and may never influence runtime,
the frozen M2, the M1–M5 shadow, paper trades, Kalshi, risk, or performance claims.
