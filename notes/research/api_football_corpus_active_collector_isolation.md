# Active Collector Isolation — API-Football Historical Corpus V1 (2026-06-26)

Active collector: main checkout `C:/Users/Mahyar/worldcup_draw_model_lab_FINAL`, branch
`v1-5-prospective-operations` @ **dc73318** (tracked-clean). WorldCupShadowCollector task = **Ready**; command
runs `scripts/windows/run_shadow_collector.ps1`, WorkingDirectory = MAIN checkout (NOT this worktree).
Heartbeat `outputs/live_shadow/collector_heartbeat.json` (alive 06:03Z, odds budget 16/500). State
`collector_state.json`. Flags KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper. Collector's live data path
is **The Odds API** (which this sprint will NOT call); it does not run the historical API-Football backfill.

This sprint works ONLY in `C:/Users/Mahyar/worldcup-api-football-corpus` on branch
`api-football-historical-corpus-v1`. It uses ONLY API-Football (no Odds API) via the existing
`ApiFootballReadOnly` adapter + a read-only key load; key never printed. Reserves API allowance for the
collector. Does NOT touch collector code/task/cadence/odds-windows/odds-budget/ledgers, frozen M1-M5, frozen
M2, B1, candidate.py, approved_models.yaml, trading/risk/Kalshi/paper, or .env. All outputs: research_only /
not_runtime_approved / not_trade_eligible / not_live_eligible.
