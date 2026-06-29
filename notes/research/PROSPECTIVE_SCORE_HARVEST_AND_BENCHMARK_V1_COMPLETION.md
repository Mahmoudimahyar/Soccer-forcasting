# Prospective Shadow Score Harvest, Result Reconciliation & Market Benchmark — V1 COMPLETION

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

**Terminal state: COMPLETE** (2026-06-29). Every fixture in the locked frozen prospective universe is
scored or explicitly excluded; benchmark reports exist; final audit passes; scorer + watchdog disabled.

## Root cause
The collector cycle calls `live_2026_shadow.py score` every 5 min but **never refreshes results**.
`score()` requires `results_2026_footballdata.csv` `status==FINISHED`; that file was stale (FINISHED only
through 2026-06-20), so all 35 predicted matches (kickoffs 06-24→06-28) stayed `TIMED` and the team-pair
join produced **0 scored rows** — written as empty metrics with rc=0 (silent false success). Demonstrated:
680/680 predictions resolve a pair; 0/680 resolve a FINISHED outcome; 35/35 predicted matches present but
`TIMED`. Failure class **#12 (result source never refreshed)** + **#8 (silent empty write)**; the other 12
candidates are demonstrably false (`prospective_score_harvest_failure_matrix.json`).

## Fix applied
An **independent, idempotent, append-only harvester** (`prospective_score_harvester_v1`) with its own
read-only result-reconciliation layer (`refresh_prospective_final_results.py`, football-data.org primary;
API-Football Pro fallback; **no Odds API**), writing only to `outputs/live_shadow/scoring_v1/`. The live
collector was **not** modified (deployment deferred — see below).

## Counts
- Frozen predictions: **680 rows**, **35 unique fixtures** (all valid, all pre-kickoff; Phase 0 manifest).
- Completed fixtures (verified final): **35 / 35**.
- Result-provider reconciliation coverage: **35/35 verified_final** (72 group fixtures pulled, 39 resolved
  to ledger ids; 33 pre-forecast MD1 matches correctly `unresolved_identity`, outside universe). Odds API
  calls: **0**. Orientation + goals consistency: OK.
- Scored fixtures (primary, one snapshot each): **34**.
- Excluded fixtures: **1** — `2026_*` with `no_common_market_snapshot` (the five market-bearing model rows
  were never co-present in one pre-kickoff snapshot for that fixture). Documented in `scoring_exclusion_ledger.csv`.

## Primary snapshot policy (preregistered, outcome-independent)
Latest common valid pre-kickoff snapshot covering all five models + the no-vig market (window preference
T-15 → T-90 → baseline). Snapshot coverage: **31 baseline, 2 final_pre_kickoff, 1 T-90**. One snapshot per
fixture; fixture-level unit; no outcome-based selection.

## Benchmark (primary, n=34, sample-size tier **C — exploratory**, 5000-sample match-level bootstrap)
| model | RPS [95% CI] | log-loss [95% CI] | draw-Brier [95% CI] |
|---|---|---|---|
| **M1_B1** (Elo, approved) | 0.1304 [0.0891, 0.1771] | 0.7754 [0.5857, 0.9860] | 0.1833 [0.1059, 0.2693] |
| **M2_market** (no-vig, read-only) | 0.1360 [0.0982, 0.1770] | 0.7740 [0.6070, 0.9521] | 0.1765 [0.1026, 0.2549] |
| M3_75_25 | 0.1304 [0.0909, 0.1762] | 0.7712 [0.5874, 0.9733] | 0.1812 [0.1076, 0.2639] |
| M4_50_50 | 0.1314 [0.0937, 0.1742] | 0.7697 [0.5943, 0.9596] | 0.1793 [0.1074, 0.2611] |
| M5_25_75 | 0.1333 [0.0945, 0.1756] | 0.7707 [0.6000, 0.9543] | 0.1778 [0.1056, 0.2611] |

- **Calibration:** observed draw rate 0.265; all models slightly under-predict draws (mean pred 0.21–0.22);
  ECE 0.074 (M5) … 0.135 (M1_B1); draw-cal slope noisy at ~9 draws (reported, not used). Reliability bins in
  `model_reliability_bins.csv`.
- **Match-level uncertainty:** fixture-level paired deltas vs B1 and vs market, match-level bootstrap.
  **Zero** of the 24 paired deltas exclude zero. CIs are wide and overlapping.

## Decision ledger (`prospective_model_decision_ledger.{json,csv}`)
- M1_B1 → `reference_only`; M2_market → `market_comparator_only`; M3/M4/M5 → `no_evidence_of_improvement`.
- **No model is runtime-ready or trade-eligible.** No model was promoted. None was manufactured a winner —
  a valid result could have favored Elo, the market, or a blend; at n=34 none does so at decision-grade.

## Deployment decision
**Independent harvester retained as the official scoring path; collector score-adapter patch DEFERRED.**
The live collector is healthy and running; patching its live score path is unnecessary because the durable
harvester fully recovers the scorecard with zero risk. Deploy/rollback scaffolds exist
(`deploy_prospective_score_adapter.ps1` dry-run-by-default; `rollback_prospective_score_adapter.ps1`).

## Durable scorer
`WorldCupProspectiveScoreHarvester` + `WorldCupProspectiveScoreHarvesterWatchdog` (15-min, append-only,
no Odds API) were installed, **proven via a real scheduled run** (LastResult 0, terminal=True), and
**disabled** at COMPLETE. Re-enable for the knockout stage (a future, not-yet-frozen universe).

## Safety attestation
- `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper` throughout. **No order, signal, edge, or trade.**
- No model fit / retrain / recalibration / selection used any 2026 outcome. Market used only as read-only comparator.
- Frozen predictions, odds, and the collector's results file were never mutated. Collector + hierarchical-transfer
  tasks untouched and healthy after all work. No secrets printed.

## Exact recommended next decision
The prospective evidence is **exploratory (Tier C, n=34) with no model–market separation**. Recommendation:
**do not change the runtime; keep B1 approved; keep M2–M5 research-only.** To reach a confirmatory tier
(50+ fixtures) re-enable the durable harvester for the **knockout stage** as those fixtures are forecast and
finalized, then re-run the benchmark. The paid-provider decision remains **deferred** — this result does not
yet justify it.
