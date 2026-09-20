# Active Collector Isolation — Research Truth Consolidation V1 (2026-06-26)

Active collector: main `C:/Users/Mahyar/worldcup_draw_model_lab_FINAL`, branch `v1-5-prospective-operations`
@ **dc73318** (tracked-clean). WorldCupShadowCollector task = **Ready**; command
`scripts/windows/run_shadow_collector.ps1`, WorkingDirectory = MAIN checkout (NOT this worktree). Heartbeat
`outputs/live_shadow/collector_heartbeat.json` (alive 17:33Z, odds 22/500). State `collector_state.json`.
Flags KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper. Live path = The Odds API (NOT used this sprint).

This sprint works ONLY in `C:/Users/Mahyar/worldcup-research-truth-fusion` on branch
`research-truth-full-corpus-xg-fusion-v1` (base tag player-impact-xg-fusion-v1 @ b30e623). The durable
controller (WorldCupResearchTruthFusionRun, <=10h) runs ONLY from this worktree, writes ONLY to
outputs/research_runs/ + gitignored raw, uses ONLY API-Football (no Odds API) + already-approved StatsBomb OPEN
data, fails closed on API/budget/collector-health failure, and marks the run INCOMPLETE (not complete) if any
hard gate is unmet. It does NOT touch collector code/task/cadence/odds-budget/ledgers, frozen M1-M5, frozen M2,
B1, candidate.py, approved_models.yaml, trading/risk/Kalshi/paper, .env, or the collector scheduler. All
outputs: research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible. No model
promoted. The collector cannot be altered from this worktree (separate path + branch; the task workdir is the
main checkout).
