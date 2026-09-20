# Active Collector Isolation — Paid Source Activation V1 (2026-06-26)

Active collector: main checkout `C:/Users/Mahyar/worldcup_draw_model_lab_FINAL`, branch
`v1-5-prospective-operations` @ **dc73318** (tracked-clean). WorldCupShadowCollector scheduled task = **Ready**;
task command runs `scripts/windows/run_shadow_collector.ps1` with WorkingDirectory = the MAIN checkout (NOT
this worktree). Heartbeat: `outputs/live_shadow/collector_heartbeat.json` (alive 2026-06-26T05:38Z, status ok,
odds budget **15/500** used). State: `collector_state.json`. Flags: KALSHI_ENABLE_LIVE_TRADING=false,
TRADING_MODE=paper.

This sprint works ONLY in worktree `C:/Users/Mahyar/worldcup-paid-source-activation` on branch
`paid-source-activation-v1`. It uses the already-paid API-Football + Odds API via read-only config (the main
root `.env`), with its OWN bounded research budgets that are SEPARATE from and additive-reserving the
collector's budget. It does NOT: alter collector code/task/cadence/odds-windows/credit-budget/ledgers, frozen
M1-M5, frozen M2, B1, candidate.py, approved_models.yaml, trading/risk/Kalshi/paper/exec, or .env/.env.example;
print/reveal/copy/hash/log/commit any key; run a second live polling loop. All outputs: research_only /
not_runtime_approved / not_trade_eligible / not_live_eligible.

## Budget reconciliation
- Collector odds budget: 15/500 used -> 485 reserved for the collector (this sprint will NOT touch its ledger).
- Research budgets (this sprint, separate accounting): API-Football Phase 1 <= 30 requests; Phase 3 <=
  min(300, 20% of verified remaining daily) or 150 if undeterminable; Odds API Phase 4 <= 30 credits total.
