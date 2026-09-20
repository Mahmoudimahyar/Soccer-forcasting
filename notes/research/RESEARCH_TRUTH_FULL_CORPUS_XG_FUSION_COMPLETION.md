# Research Truth Consolidation + Full Corpus + Dynamic xG/Player-State Fusion V1 — INCOMPLETE

research_only=true · experimental=true · not_runtime_approved=true · not_trade_eligible=true ·
not_live_eligible=true · KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

**STATUS: INCOMPLETE — NOT tagged complete.** Per the sprint's explicit anti-shortcut mandate, the completion
tag is withheld because multiple Phase-10 hard gates are objectively FALSE against current manifests. This run
honestly reaches the INCOMPLETE terminal state (Phase 11 incomplete path) with the exact resume state preserved.

Worktree `C:/Users/Mahyar/worldcup-research-truth-fusion`, branch `research-truth-full-corpus-xg-fusion-v1`
(base tag player-impact-xg-fusion-v1 @ b30e623).

## What is DONE (verifiable, committed)
- **Canonical truth registry** (Phase 0): built by scanning ACTUAL gitignored raw across all worktrees (not
  trusting summaries). Resolves every conflicting claim:
  - AF fixtures: **1,180 distinct fixtures with event files** (900 corpus + ~220 deep-research ext + 60
    player-history). "900"/"1120" were scope-correct subsets.
  - Sendings-off: **123** (900-corpus) and **176** (1,120 incl. extension) — both correct for their scope.
  - Player-history corpus: **60 / 2,000 = 3%** complete (1,940 outstanding).
  - StatsBomb: **258** exact bridge matches, **60** with raw events (23%), **0** joined to dynamic snapshots.
  - `data/reference/research_truth_registry.{json,csv}`, `research_truth_registry_report.md`,
    `research_claim_verification_ledger.md` (the prior player-impact negative is downgraded to
    **incomplete_or_partial -> needs_rerun** — valid only for the 3% partial implementation).
- **Execution manifest** (Phase 1): the predeclared 2,000-fixture manifest with per-fixture state;
  **manifest_completion_rate = 0.03**; gate #2 (>=95%) NOT met. No substitute sample used.
- **Durable 10h controller config + 16-job queue + runbook + one-time-task scripts** (reuse of the proven
  restart-safe supervisor).

## Objective Phase-10 hard-gate status (the reason for INCOMPLETE)
| gate | required | actual | met |
|---|---|---|---|
| #1 truth registry verifies counts | exists | built | YES |
| #2 AF manifest completion | >=95% | **3%** | **NO** |
| #5 StatsBomb cache completion | >=90% | **23%** | **NO** |
| #6 xG snapshot join nonzero | >0 | **0** | **NO** |
| #15 collector unchanged | yes | dc73318 clean, Ready | YES |
| #16 B1/M1-M5/M2/trading/Kalshi unchanged | yes | unchanged | YES |
Gates #3,4,7-14 are downstream of #2/#5/#6 and therefore not yet evaluable.

## Why completion is genuinely multi-day (external constraint, not a shortcut)
Completing the AF corpus = events+lineups for **1,940 outstanding fixtures ≈ 3,880 API-Football requests**.
Under the budget policy (reserve max(1500, 25% of remaining)), one day's research budget (~3,000-3,477) cannot
cover 3,880 requests -> the corpus completion is **daily-quota-bounded / multi-day**. Plus 198 StatsBomb event
files + the xG-snapshot join + the dynamic-snapshot rebuild + 30 leakage tests + the full preregistered eval
(R0-R2/P1-P5, N0-N4, C0-C2, X0-X3) + ablations remain to build/run. This exceeds a single interactive turn.

## Controller / API / safety
No durable run was started to a complete terminal state (the gates cannot be met in one window). API-Football
requests this session: **0** new (registry + manifest are read-only scans of existing raw). **No Odds API.**
`pytest -q` = 265 passed / 20 skipped. `git diff dc73318..HEAD` = 130 added / 1 modified (inherited conftest).
Raw gitignored (0 tracked). No key revealed. Collector **dc73318, clean, Ready** (untouched). B1 sole runtime;
M1-M5 + frozen M2 + candidate.py + approved_models.yaml + trading/risk/Kalshi/paper unchanged. No model trained.

## Exact next step (resume — see RESEARCH_TRUTH_FUSION_RESUME_NEXT_TASK.md)
1. Advance the AF corpus daily (`python scripts/player_history_resume.py`) until execution-manifest >=95%.
2. Complete the StatsBomb event cache (258 bridge -> >=90% with events).
3. Build the **xG-snapshot JOIN** (Phase 6, the key missing engineering piece) + dynamic snapshot datasets
   (Phase 4, 30 tests) + full temporal priors (Phase 5).
4. Build rt_jobNN wrappers + run the durable 10h controller; verify ALL Phase-10 gates; only THEN tag complete.

## Why active collector, B1, M1-M5, frozen M2, paper trading, trading, Kalshi, and risk remain unchanged
This sprint is historical research consolidation + a planned (not-yet-complete) completion run. Nothing was
trained for promotion; nothing live/trade-eligible was produced; the collector was never written to. Honesty
over optimism: the partial prior result is flagged needs_rerun, and the completion is honestly declared INCOMPLETE
rather than forced.
