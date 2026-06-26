# Active Collector Isolation — Deep Research Controller V1 (2026-06-26)

Active collector: main checkout `C:/Users/Mahyar/worldcup_draw_model_lab_FINAL`, branch
`v1-5-prospective-operations` @ **dc73318** (tracked-clean). WorldCupShadowCollector task = **Ready**; command
`scripts/windows/run_shadow_collector.ps1`, WorkingDirectory = MAIN checkout (NOT this worktree). Heartbeat
`outputs/live_shadow/collector_heartbeat.json` (alive 06:53Z, odds 16/500). State `collector_state.json`.
Flags KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper.

This sprint works ONLY in `C:/Users/Mahyar/worldcup-deep-research` on branch
`deep-research-inplay-foundation-v1` (based on tag api-football-historical-corpus-v1 @ 6ddf60a). It builds a
restart-safe, bounded (<=4h) research controller (WorldCupDeepResearchNightRun) that runs ONLY from this
worktree, writes ONLY to outputs/research_runs/ + gitignored raw, uses ONLY API-Football (no Odds API), and
fails closed on API/budget/collector-health failure. It does NOT touch collector code/task/cadence/odds-budget/
ledgers, frozen M1-M5, frozen M2, B1, candidate.py, approved_models.yaml, trading/risk/Kalshi/paper, .env, or
the collector scheduler task. All outputs: research_only / experimental / not_runtime_approved /
not_trade_eligible / not_live_eligible. The controller monitors the collector heartbeat and STOPS if it goes
stale (it never writes to it).
