# Prospective Score Harvester — Operations Guide

The harvester recovers and scores the **frozen prospective predictions** the Shadow Collector produces, and
benchmarks the approved model **B1** against the **no-vig market** and the **M1–M5 blends** — all
**research-only, paper-only, append-only**. It exists because the collector's built-in `score` step silently
produced nothing.

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

---

## Why it exists (the bug it fixes)

The collector cycle calls `live_2026_shadow.py score` every 5 min, but **nothing in the cycle refreshes
results**. `score()` filters `data/processed/results_2026_footballdata.csv` to `status==FINISHED`; that file
went stale (FINISHED only through an early matchday), so every later predicted match stayed `TIMED` and the
join produced **0 scored rows**, written as empty metrics with `rc=0` (a silent false success). Full forensics:
[`notes/research/prospective_score_harvest_root_cause_audit.md`](../notes/research/prospective_score_harvest_root_cause_audit.md)
and `data/reference/prospective_score_harvest_failure_matrix.json`.

The harvester fixes this by **refreshing verified-final results itself** and scoring in an isolated,
idempotent, append-only path — without modifying the live collector, the frozen predictions, or any model.

---

## Pipeline (what each script does)

| Step | Script | Reads | Writes |
|---|---|---|---|
| Forensic freeze | `scripts/prospective_harvest/phase0_forensic_freeze.py` | predictions, queue, raw odds | `data/reference/prospective_frozen_input_manifest.{json,csv}` |
| Result refresh | `scripts/refresh_prospective_final_results.py` | football-data.org (API-Football fallback) | `outputs/live_shadow/scoring_v1/results/` |
| Reconciliation audit | `scripts/audit_prospective_result_reconciliation.py` | refreshed results | `.../results/reconciliation_audit.json` |
| Snapshot selection | `scripts/select_primary_prospective_snapshots.py` | predictions | `.../primary_snapshot_registry.csv` |
| Score harvest | `scripts/prospective_score_harvester_v1.py` | predictions + results + selection | `.../scored_prediction_rows.*`, `model_metrics.csv`, `scoring_integrity_audit.json`, … |
| Benchmark | `scripts/prospective_benchmark_v1.py` | scored rows | `notes/research/PROSPECTIVE_*_V1.md`, `data/reference/prospective_model_decision_ledger.{json,csv}` |
| Durable runner | `scripts/run_prospective_score_harvester.py` | (orchestrates refresh+harvest) | heartbeat/state/log under `scoring_v1/` |
| Watchdog | `scripts/prospective_score_harvester_watchdog.py` | scorer health + integrity | `.../watchdog_state.json` |

Run them in order, or just run the **durable runner** which does refresh-if-needed → harvest in one bounded cycle.

---

## Run it

```bash
# one bounded cycle (recommended)
python scripts/run_prospective_score_harvester.py

# or full pipeline
python scripts/refresh_prospective_final_results.py
python scripts/audit_prospective_result_reconciliation.py
python scripts/select_primary_prospective_snapshots.py
python scripts/prospective_score_harvester_v1.py
python scripts/prospective_benchmark_v1.py
```

**Durable scheduling (Windows, every 15 min):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install_prospective_score_harvester_tasks.ps1   # install
powershell -File scripts\windows\uninstall_prospective_score_harvester_tasks.ps1                          # remove
```
On Linux/macOS, schedule `run_prospective_score_harvester.py` and `prospective_score_harvester_watchdog.py`
via cron (15-min) — see [`CRON_SETUP.md`](CRON_SETUP.md).

**Where the inputs come from:** the harvester reads the collector's immutable artifacts. In a single clone it
reads them from this repo. If the collector lives elsewhere, set `PSH_COLLECTOR_ROOT` to that checkout's path.

---

## Guarantees (enforced + tested)

- **Idempotent / append-only.** Score key = `prediction_id + final_result_hash + scorer_version`. Re-runs add
  nothing new; a *corrected* final result is **appended** (prior row preserved), never silently rewritten.
- **Hard gates per scored row:** `prediction_timestamp < kickoff`; market snapshot `<= prediction_timestamp`
  (no future odds); result must be `verified_final`; probabilities must sum to 1; identity must resolve.
- **One primary snapshot per fixture** — the latest common valid pre-kickoff snapshot covering all five
  models + the market (preregistered, outcome-independent:
  [`prospective_score_harvest_preregistration.md`](../notes/research/prospective_score_harvest_preregistration.md)).
- **Empty cohort → explicit `no_eligible_rows` state**, never a false success.
- **Never** calls the Odds API, mutates frozen predictions/odds, refits/recalibrates/selects a model, or uses
  a 2026 outcome in any fit. Market is a read-only comparator.
- Integrity is self-checked each run: `outputs/live_shadow/scoring_v1/scoring_integrity_audit.json` → `all_ok`.

Tests: `tests/test_prospective_result_reconciliation.py`, `test_prospective_snapshot_selection.py`,
`test_prospective_score_harvester.py` (33 deterministic cases).

---

## Reading the benchmark

- `outputs/live_shadow/scoring_v1/model_metrics.csv` — per-model RPS, log-loss, Brier components, ECE,
  draw-calibration slope/intercept, sharpness, predicted-vs-observed draw rate.
- `outputs/live_shadow/scoring_v1/benchmark_model_metrics_ci.csv` — bootstrap 95% CIs.
- `outputs/live_shadow/scoring_v1/benchmark_paired_deltas.csv` — fixture-level paired deltas vs B1 and vs market.
- `data/reference/prospective_model_decision_ledger.csv` — each model's honest classification
  (`reference_only` / `market_comparator_only` / `no_evidence_of_improvement` / `exploratory_underpowered` / …).
- Human reports: `notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md`, `..._MARKET_BENCHMARK_V1.md`, `..._CALIBRATION_AND_RELIABILITY_V1.md`.

**Sample-size tiers** (printed by the harvester): A `<10` smoke-test · B `10–19` descriptive · C `20–49`
exploratory · D `50+` confirmatory. **No tier promotes a model to runtime.** Interpret accordingly — small
samples have wide, overlapping CIs.

---

## Extending to the knockout stage

The current locked universe is the **group stage**. As knockout fixtures are forecast and finalized:
1. Let the collector freeze knockout predictions (re-enable `WorldCupShadowCollector`).
2. Re-enable the harvester task (`Enable-ScheduledTask -TaskName WorldCupProspectiveScoreHarvester`) or run a cycle.
3. The result reconciler already encodes extra-time / shootout semantics (a regulation 1X2 draw is **not**
   converted by a shootout). Re-run the benchmark; more fixtures move the sample toward a confirmatory tier.

The durable runner writes a **terminal** state once every fixture in the locked universe is scored or
explicitly excluded; the watchdog then takes no action. Disable the tasks when you're done.
