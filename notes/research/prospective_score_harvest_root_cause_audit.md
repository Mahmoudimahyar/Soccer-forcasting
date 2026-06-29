# Prospective Score Harvest — Root-Cause Forensic Audit (Phase 1)

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

## Question
Why does the collector's `score` command return success every 5 minutes but write no scored rows, leaving
`live_2026_shadow_metrics.csv`, `..._calibration.csv`, and `prospective_scorecard.csv` empty?

## Score path traced end-to-end
`shadow_collector_cycle.py` → `subprocess(live_2026_shadow.py score)` → `score()` reads
`outputs/research/live_2026_shadow_predictions.csv` (680 rows) and
`data/processed/results_2026_footballdata.csv` → filters results to `status=="FINISHED"` → builds
`pair = frozenset(canon(team_a), canon(team_b))` → maps `match_id → pair` (via forecast_targets) →
`pair → outcome` → `scored = preds[outcome.notna()]` → groups by model → writes metrics. **No step in the
cycle refreshes the results file.**

## Demonstrated from actual artifacts (not assumed)
- 680 / 680 predictions resolve a team-pair; **0 / 680 resolve a FINISHED outcome.**
- All 35 predicted fixtures are present in the results file, but **35 / 35 carry `status=TIMED`** there.
- The results file's FINISHED rows span only **2026-06-11 → 2026-06-20**; TIMED rows span 06-20 → 06-28
  (i.e., every predicted match, kickoffs 06-24 → 06-28).
- Only `scripts/fetch_footballdata_2026.py` writes that file; the collector cycle never calls it, so the
  file is frozen at its last manual fetch. A live football-data.org refresh now returns **72/72 FINISHED**.

## Primary root cause
**#12 — the result source is never refreshed inside the score path.** This manifests as a stale FINISHED
filter (analog of #2) and is masked by a **silent empty write with rc=0 (#8)**. All other 11 candidate
paths are demonstrably false (see `prospective_score_harvest_failure_matrix.json`): fixture identity,
team-name normalization, UTC drift, output path, model identity, snapshot parsing, ET/shootout semantics,
swallowed exceptions — none apply. Severity: **critical** (blocks all scoring); **partial vs total:** total.

## Remediation (implemented, this program)
1. `refresh_prospective_final_results.py` — read-only verified-final refresh (football-data.org primary;
   API-Football Pro fallback; **no Odds API**), written to an isolated scoring root.
2. `prospective_score_harvester_v1.py` — idempotent, append-only scorer; explicit `no_eligible_rows` state
   (never a silent false success); integrity audit.
3. Durable `WorldCupProspectiveScoreHarvester` runs refresh-if-needed + harvest each 15 min.
4. The live collector is **not** modified (see deployment decision); its harmless empty-metrics write does
   not affect frozen predictions or odds capture.

## Regression coverage
`test_prospective_result_reconciliation.py` (stale TIMED excluded; identity by pair; date shift),
`test_prospective_score_harvester.py` (empty cohort explicit state; verified-final required; idempotent;
first-write-wins; correction append). 33 tests pass.
