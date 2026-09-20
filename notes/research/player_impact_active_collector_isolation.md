# Active Collector Isolation — Player-Impact & xG Fusion V1 (2026-06-26)

Active collector: main `C:/Users/Mahyar/worldcup_draw_model_lab_FINAL`, branch `v1-5-prospective-operations`
@ **dc73318** (tracked-clean). WorldCupShadowCollector task = **Ready**; command
`scripts/windows/run_shadow_collector.ps1`, WorkingDirectory = MAIN checkout (NOT this worktree). Heartbeat
`outputs/live_shadow/collector_heartbeat.json` (alive 07:33Z, odds 16/500). State `collector_state.json`.
Flags KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper. Live path = The Odds API (this sprint will NOT
call it). API-Football used historically only (read-only adapter).

This sprint works ONLY in `C:/Users/Mahyar/worldcup-player-impact-xg` on branch `player-impact-xg-fusion-v1`
(base tag deep-research-inplay-foundation-v1 @ 6136443). It reuses the restart-safe bounded controller for a
<=6h run (WorldCupPlayerImpactResearchRun) that writes ONLY to outputs/research_runs/ + gitignored raw, uses
ONLY API-Football (no Odds API) + already-approved StatsBomb OPEN data (CC-licensed, attribution), and fails
closed on API/budget/collector-health failure. It does NOT touch collector code/task/cadence/odds-budget/
ledgers, frozen M1-M5, frozen M2, B1, candidate.py, approved_models.yaml, trading/risk/Kalshi/paper, .env, or
the collector scheduler. All outputs: research_only / experimental / not_runtime_approved / not_trade_eligible /
not_live_eligible. No model trained for promotion.
