# Active Collector Isolation — Structured Event Procurement Readiness V1 (2026-06-26)
Active collector: main checkout C:/Users/Mahyar/worldcup_draw_model_lab_FINAL, branch
v1-5-prospective-operations @ dc73318 (tracked-clean). WorldCupShadowCollector scheduled task = Ready;
task command runs scripts/windows/run_shadow_collector.ps1 with WorkingDirectory = the MAIN checkout (NOT
this worktree). Heartbeat: outputs/live_shadow/collector_heartbeat.json (alive 2026-06-26T05:18Z, status ok).
State: collector_state.json. Trading flags: KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper.
This sprint works ONLY in worktree C:/Users/Mahyar/worldcup-structured-event-readiness on branch
structured-event-procurement-readiness-v1. NO purchases, trials, forms, scraping, login bypass, credentials,
or provider/Odds/API-Football calls. No edits to collector code/task/odds-budget/cadence, frozen M1-M5,
frozen M2, B1, candidate.py, approved_models routing, trading/risk/Kalshi/paper, ledgers, or .env. All
outputs: research_only / not_runtime_approved / not_trade_eligible / not_live_eligible.
