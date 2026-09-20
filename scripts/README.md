# `scripts/` index

This folder holds **369 scripts from the research period** (2026-06-20 to 2026-06-29): 320 Python, 47
PowerShell and 2 shell scripts. 205 sit at the top level; 164 sit in nine subfolders (seven staged job
queues, the score-harvester internals, and the Windows Task Scheduler wrappers). One more file,
[`make_readme_figures.py`](make_readme_figures.py), was added on 2026-09-20 to draw the README figures. It
is not part of those counts and is listed in [section 15](#15-repository-hygiene).

Most of these files are **a record of how the research was run**, not a toolkit you are expected to run
end to end. The reusable library lives in [`../src/wcdrawlab/`](../src/wcdrawlab/); the results live in
[`../notes/research/`](../notes/research/README.md) and [`../data/reference/`](../data/reference/README.md).
This page tells you which handful of scripts are real entry points, how the rest chain together, and what
each one needs before it will do anything.

Everything here is **research-only and paper-only**. No script places an order, and none imports the
dormant, never-armed trading scaffold in `src/wcdrawlab/trading/`. All outputs are forecast-quality metrics,
never profit and loss. Nothing on this page is betting or financial advice.

Terms such as B1, M1–M5, LOCO, RPS and dRPS are defined in [`../docs/GLOSSARY.md`](../docs/GLOSSARY.md).
Two namespaces collide: the pre-match shadow models M1–M5 (where **M2_market** is the no-vig bookmaker
consensus) and the in-play models M0–M6 (where **in-play M2** is the remaining-time Poisson).

## Contents

- [Read this before running anything](#read-this-before-running-anything)
- [Entry points you would actually run](#entry-points-you-would-actually-run)
- [1. Setup and shared helpers](#1-setup-and-shared-helpers)
- [2. Data acquisition and provider probes](#2-data-acquisition-and-provider-probes)
- [3. Pre-match tables, baselines, market studies and forecasts](#3-pre-match-tables-baselines-market-studies-and-forecasts)
- [4. Prospective 2026 shadow operations](#4-prospective-2026-shadow-operations)
- [5. In-play replay, evaluation and the holdout freeze](#5-in-play-replay-evaluation-and-the-holdout-freeze)
- [6. API-Football corpus, player history and player-impact evaluations](#6-api-football-corpus-player-history-and-player-impact-evaluations)
- [7. StatsBomb bridge, xG state and the dynamic in-play panel](#7-statsbomb-bridge-xg-state-and-the-dynamic-in-play-panel)
- [8. Event-process, residual-intensity and evidence-power builders](#8-event-process-residual-intensity-and-evidence-power-builders)
- [9. International Event Lake](#9-international-event-lake)
- [10. Hierarchical club-to-international transfer](#10-hierarchical-club-to-international-transfer)
- [11. Commentary NLP (SoccerNet, club football)](#11-commentary-nlp-soccernet-club-football)
- [12. Supervisors, watchdogs and run launchers](#12-supervisors-watchdogs-and-run-launchers)
- [13. Staged job queues (seven subfolders)](#13-staged-job-queues-seven-subfolders)
- [14. `prospective_harvest/` and `windows/`](#14-prospective_harvest-and-windows)
- [15. Repository hygiene](#15-repository-hygiene)
- [Read-only audits: which ones gate and which ones only report](#read-only-audits-which-ones-gate-and-which-ones-only-report)
- [Exploratory analyses that are not tests](#exploratory-analyses-that-are-not-tests)
- [Two scripts fixed on 2026-09-20](#two-scripts-fixed-on-2026-09-20)

---

## Read this before running anything

**1. The 2026 World Cup group stage is over.** The collector and harvester below are documented so the
method can be inspected and reused. A fresh clone cannot regenerate the 2026 ledger: the frozen
predictions, raw odds snapshots and everything under `outputs/`, `data/raw/` and `data/processed/` are
gitignored runtime artifacts. Only their hashes, manifests and the resulting reports are tracked.

**2. Many scripts are single-machine orchestration records.** 64 files in this folder are tied to the
author's machine: 53 contain absolute Windows paths to per-research-line git worktrees, and 11 more refer
to the collector checkout by folder name (usually as a guard that refuses to touch it). That covers the
research-line launchers (`run_*.ps1`), every research-run installer in `windows/`, the four research
watchdogs, several job-queue helpers, and a number of builders and audits. Other scripts reach the same
paths indirectly through the roots configs in [`../configs/`](../configs/). These files document exactly
what was run; they will not run elsewhere without editing those roots. This is historical provenance,
recorded as item E7 in [`../docs/ERRATA.md`](../docs/ERRATA.md). The portable exceptions are the shadow
collector and the score harvester (sections 4 and 14), which resolve the repo root from their own
location.

**3. Know what a script costs before you start it.** The "Needs" column in every table uses these words:

| Word | Meaning |
|---|---|
| offline | Reads local files only. Most need gitignored datasets that an earlier step builds. |
| net | Downloads from an open source (GitHub-hosted open data, Hugging Face). No key, no quota. |
| `ODDS_API_KEY` | Calls The Odds API. **Spends credits.** Historical-endpoint calls cost 10 credits per region per market, per the scripts' own docstrings. |
| `API_FOOTBALL_KEY` | Calls API-Football. **Spends daily request quota.** The corpus and player-history backfills go through the read-only adapter with a hard request cap; the older fetchers throttle and cache instead. |
| `FOOTBALL_DATA_KEY` | Calls football-data.org (rate-limited free tier) for fixtures and final results. |
| gate | Read-only check that **exits non-zero on violation**. |
| report | Read-only check that writes or prints findings and exits 0 either way. |

Most fetchers load keys from `.env` through [`_live_env.py`](_live_env.py); the harvester has an equivalent
loader in `prospective_harvest/_harvest_common.py`. Both print key *names* only, never values.

> [!WARNING]
> Assume that any script whose "Needs" cell names a key **calls the provider as soon as it starts**. Rows
> marked "spends on launch" have no dry-run flag and no cap flag at all. The API-Football backfills also
> start immediately, but stop at their request cap (`--max-requests`, or the budget shown in the table).
>
> Only a few scripts are safe by default and plan until told otherwise: `fetch_odds_live_2026.py`,
> `prospective_collect.py`, `prospective_score.py` and `commentary_sample_acquire.py` (need `--execute`),
> and the `run_prospective_collection` wrappers (need `EXECUTE=1`). Three more offer an opt-in `--dry-run`
> that you must pass yourself: `windows/shadow_collector_cycle.py`, `five_hour_supervisor.py` and
> `ingest_api_football_historical.py`.

**4. Re-running a report script overwrites tracked files.** Builders and benchmark scripts write fixed
filenames under `notes/research/` and `data/reference/`. Those committed files are the historical record.
Work on a branch if you re-run them.

**5. Do not rename scripts.** Tests import or reference several of them by filename (for example
`deep_research_supervisor.py`, `build_research_table.py`, `build_international_event_lake_cohort.py`,
`check_secret_hygiene.py` and the `research_jobs/pi_job*.py` queue).

---

## Entry points you would actually run

These come from [`../QUICKSTART.md`](../QUICKSTART.md) and the runbooks in [`../docs/`](../docs/README.md).
Run them from the repository root. Open inputs are downloaded first with
`python -m wcdrawlab.cli fetch-public`, or the equivalent
[`../examples/fetch_public_data.py`](../examples/fetch_public_data.py) (network, no key).

| # | Script | One line | Needs |
|---|---|---|---|
| 1 | [`setup_claude_code.sh`](setup_claude_code.sh) | Optional bootstrap: create a venv, install, run `pytest -q`. | net (pip) |
| 2 | [`check_secret_hygiene.py`](check_secret_hygiene.py) | Confirms `.env.example` holds placeholders only; prints names, never values. | offline, gate |
| 3 | [`build_research_table.py`](build_research_table.py) | Builds the leakage-tested research table, the 2026 forecast targets and the walk-forward Elo history. | offline (open data already downloaded) |
| 4 | [`tier2_baselines.py`](tier2_baselines.py) | Baseline suite B0–B7 on the fixed folds with a paired bootstrap against B1 (the Tier-2 gate). | offline, but the 2022 fold reads `data/processed/market_features_2022.csv` without a fallback, so the run stops there unless that file exists (it is built by the paid `fetch_historical_odds_2022.py`) |
| 5 | [`forecast_runtime.py`](forecast_runtime.py) | The approved runtime forecast. Routes through the model registry; B1 is the only approved model. | offline |
| 6 | [`build_future_2026_queue.py`](build_future_2026_queue.py) | Builds the queue of not-started 2026 fixtures with pre-match Elo anchors. **Overwrites the tracked `data/reference/future_2026_prospective_queue.csv`**; rebuilt after the tournament, no fixture is eligible. Skip it unless you mean to. | `API_FOOTBALL_KEY` (adapter budget 50 requests, reserve 10) |
| 7 | [`windows/shadow_collector_cycle.py`](windows/shadow_collector_cycle.py) | One bounded collector cycle: odds snapshot if due, freeze M1–M5, score. Start with `--dry-run`. Exits 3 unless `KALSHI_ENABLE_LIVE_TRADING=false` and `TRADING_MODE=paper`. | `ODDS_API_KEY` (1 credit per snapshot, 500-credit ceiling); nothing in `--dry-run` |
| 8 | [`windows/install_shadow_collector_task.ps1`](windows/install_shadow_collector_task.ps1) | Registers the 5-minute `WorldCupShadowCollector` task. Portable. Its default hard end (`-HardEndUtc`, 2026-07-05) has passed, so reuse needs a new value. | Windows |
| 9 | [`run_prospective_score_harvester.py`](run_prospective_score_harvester.py) | One bounded harvester cycle: lock, refresh final results if needed, score, write state. Never calls The Odds API. | `FOOTBALL_DATA_KEY` only while results are non-final |
| 10 | [`refresh_prospective_final_results.py`](refresh_prospective_final_results.py) | Harvester step 1: verified-final results from football-data.org. `--offline` skips the fetch. | `FOOTBALL_DATA_KEY` |
| 11 | [`audit_prospective_result_reconciliation.py`](audit_prospective_result_reconciliation.py) | Step 2: every predicted fixture has a verified-final result, orientation is consistent. | offline, gate (exit 2) |
| 12 | [`select_primary_prospective_snapshots.py`](select_primary_prospective_snapshots.py) | Step 3: one snapshot per fixture by the pre-specified, outcome-independent rule. | offline |
| 13 | [`prospective_score_harvester_v1.py`](prospective_score_harvester_v1.py) | Step 4: idempotent, append-only scoring; first write wins per score key. | offline |
| 14 | [`prospective_benchmark_v1.py`](prospective_benchmark_v1.py) | Step 5: B1 vs no-vig market vs fixed blends, match-level bootstrap CIs, decision ledger. **Overwrites the tracked `PROSPECTIVE_*` reports**, including the early-line caveat banners added to them on 2026-09-20. | offline |
| 15 | [`windows/install_prospective_score_harvester_tasks.ps1`](windows/install_prospective_score_harvester_tasks.ps1) | Registers the 15-minute harvester task and its watchdog. Portable. | Windows |

The fixed evaluator is not in this folder. It is `python -m wcdrawlab.research.runner`, run exactly as
written in [`../program.md`](../program.md).

---

## 1. Setup and shared helpers

4 files. Small modules that other scripts import, plus the bootstrap script.

| Script | What it does | Needs |
|---|---|---|
| [`setup_claude_code.sh`](setup_claude_code.sh) | venv, `pip install -r requirements.txt`, `pip install -e .`, `pytest -q`. Moved here from the repository root on 2026-09-20. | net (pip) |
| [`_live_env.py`](_live_env.py) | Loads keys from `.env` (then `.env.example` as a fallback) into the process; reports names only. | offline |
| [`_lakejob.py`](_lakejob.py) | Path bootstrap and CSV/JSON writers for the event-lake scripts. | offline |
| [`_lake_catalog_util.py`](_lake_catalog_util.py) | Catalogue and match-list reads from the official StatsBomb open-data host; strict team/date normalisation. | net |

## 2. Data acquisition and provider probes

17 files. Each fetcher writes raw snapshots under gitignored `data/raw/` and a normalised table under
gitignored `data/processed/`. Source terms and licences are in
[`../docs/DATA_SOURCES.md`](../docs/DATA_SOURCES.md) and
[`../docs/DATA_SOURCE_GOVERNANCE.md`](../docs/DATA_SOURCE_GOVERNANCE.md).

```text
fetch_*  ->  data/raw/...  ->  build_* (section 3)  ->  data/processed/...
```

| Script | What it does | Needs |
|---|---|---|
| [`provider_health_check.py`](provider_health_check.py) | Status table for every configured provider using free or negligible endpoints; no secret printed. | all three keys (optional) |
| [`probe_apis.py`](probe_apis.py) | Connectivity probe for The Odds API and API-Football; prints plan and remaining quota. | `ODDS_API_KEY`, `API_FOOTBALL_KEY` (one fixtures request) |
| [`ingest_dry_run.py`](ingest_dry_run.py) | Read-only ingestion command; `--dry-run` produces a checked plan and writes nothing. | offline |
| [`ingest_api_football_historical.py`](ingest_api_football_historical.py) | Season-gated, quota-metered historical ingestion; fails closed outside seasons 2022–2024; `--dry-run` capable. | `API_FOOTBALL_KEY` |
| [`fetch_fifa_rankings.py`](fetch_fifa_rankings.py) | Open FIFA ranking history (1992–2024) normalised to the project schema. | net |
| [`fetch_footballdata_2026.py`](fetch_footballdata_2026.py) | 2026 group structure and latest results; cross-checks the reconstructed groups. | `FOOTBALL_DATA_KEY` |
| [`fetch_statsbomb_xg.py`](fetch_statsbomb_xg.py) | Per-shot xG timelines from StatsBomb Open Data; keeps shot events only. | net |
| [`acquire_statsbomb_open.py`](acquire_statsbomb_open.py) | StatsBomb open events for the men's international competitions that overlap the API-Football corpus. | net |
| [`build_statsbomb_catalog.py`](build_statsbomb_catalog.py) | Full StatsBomb Open Data competition catalogue with suitability labels. | net |
| [`fetch_odds_2026.py`](fetch_odds_2026.py) | One timestamped 2026 World Cup odds snapshot. | `ODDS_API_KEY`, spends on launch |
| [`fetch_historical_odds_2022.py`](fetch_historical_odds_2022.py) | 2022 group-stage pre-kickoff odds, normalised to a no-vig consensus (baseline B6 for the 2022 fold). | `ODDS_API_KEY`, historical endpoint, spends on launch |
| [`fetch_intl_odds.py`](fetch_intl_odds.py) | Pre-kickoff odds for senior men's internationals 2020–2025; resumable (skips saved slots). | `ODDS_API_KEY`, historical endpoint, spends on launch |
| [`fetch_intl_odds_sharp.py`](fetch_intl_odds_sharp.py) | Closing-line and Pinnacle snapshots for the same matches. | `ODDS_API_KEY`, historical endpoint, spends on launch |
| [`odds_historical_pilot_v2.py`](odds_historical_pilot_v2.py) | Diagnostic pilot: two snapshots for six predeclared 2022 fixtures, capped at 30 credits. | `ODDS_API_KEY`, spends on launch |
| [`validate_odds_pilot_2022.py`](validate_odds_pilot_2022.py) | Data-quality check of the 2022 matchday-1 odds from files already on disk. Spends nothing. | offline, report |
| [`fetch_player_plane.py`](fetch_player_plane.py) | Lineups, per-player stats and team statistics for a competition; append-only, throttled, `--max-calls`. | `API_FOOTBALL_KEY` (Pro plan) |
| [`audit_public_data.py`](audit_public_data.py) | One-shot inventory of the downloaded public datasets: coverage, schema, duplicates. | offline, report |

## 3. Pre-match tables, baselines, market studies and forecasts

30 files. This is the oldest line (2026-06-20 onward) and the one that produced the only runtime-approved
model, B1.

```text
build_research_table -> evaluate_baselines / tier2_baselines -> (B1 approved) -> forecast_runtime
                     -> autoresearch_batch / elo_research / fifa_research   (early cycles; touched the 2022 gate)
                     -> research_sweep / research_exp_draw                  (the one dev-only 20-experiment cycle)
fetch_*odds* -> build_market_features / build_intl_dataset -> market studies (2022, auxiliary internationals)
```

Verified outcome: on the pooled dev folds (144 matches, 2,000-resample paired bootstrap) there was no
evidence that any baseline improves on plain Elo. B7 vs B1: dRPS +0.0011, 95% CI [−0.0059, +0.0077], where
dRPS is the paired RPS difference, candidate minus B1, and a negative value would favour the candidate.
The only significant differences belonged to B0 and B2, which were worse. This is a statement about the
pooled dev folds, not a claim that B1 is best everywhere: on the single-read 2022 gate it ranked fifth of
nine by composite score. See
[`../notes/research/tier_2_baseline_gate.md`](../notes/research/tier_2_baseline_gate.md).

**Tables and provenance**

| Script | What it does | Needs |
|---|---|---|
| [`build_research_table.py`](build_research_table.py) | Research modelling table (World Cup group matches 1998–2026), 2026 forecast targets, Elo history, reconstructed groups. | offline |
| [`build_source_provenance.py`](build_source_provenance.py) | Registry of every external source with hash, coverage, licence and intended use (the one tracked file under `data/processed/`). | offline |
| [`build_market_features.py`](build_market_features.py) | Raw odds snapshot to no-vig consensus features, mapped to 2026 fixtures. | offline |
| [`build_intl_dataset.py`](build_intl_dataset.py), [`build_intl_sharp_dataset.py`](build_intl_sharp_dataset.py) | Join auxiliary international odds (and the closing/Pinnacle lines) to results and time-safe Elo. | offline |

**Baselines and the autoresearch cycle**

| Script | What it does | Needs |
|---|---|---|
| [`tier2_baselines.py`](tier2_baselines.py) | B0–B7 on dev folds 2010/2014/2018, a single read of the 2022 gate, 2026 matchday 1 locked; paired bootstrap vs B1. | offline; needs `market_features_2022.csv` for the 2022 fold |
| [`evaluate_baselines.py`](evaluate_baselines.py) | Earlier B0–B7 evaluation across the full fold hierarchy. | offline |
| [`research_eval.py`](research_eval.py) | Convenience wrapper: per-fold and mean composite for a config. Does not modify the fixed evaluator. | offline |
| [`research_sweep.py`](research_sweep.py) | The 18-combination candidate sweep on dev folds, without editing `candidate.py`. | offline |
| [`research_exp_draw.py`](research_exp_draw.py) | Train-only draw recalibration on top of the V8 candidate. | offline |
| [`autoresearch_batch.py`](autoresearch_batch.py) | Early batch exploration of the candidate surface. Judged on the 2018 and 2022 folds, which is the gate contact noted below. | offline |
| [`elo_research.py`](elo_research.py), [`fifa_research.py`](fifa_research.py) | Elo construction variants; FIFA-ranking features. Both rejected. Both also selected on 2018 + 2022. | offline |
| [`eval_scoreline.py`](eval_scoreline.py) | Poisson and Dixon-Coles scoreline ablation. Did not improve 1X2. | offline |

Every variant in the single 20-experiment cycle was rejected under the pre-set 0.002 threshold, and
`candidate.py` was left unchanged. Note that the early cycles touched the 2022 gate when choosing the V8
architecture and blend weight; that contamination was caught and selection was re-established on dev
folds only, with 2022 read once
([`../notes/research/tier_2_existing_work_audit.md`](../notes/research/tier_2_existing_work_audit.md)).

**Market studies (retrospective, exploratory)**

| Script | What it does | Needs |
|---|---|---|
| [`backtest_2022_market.py`](backtest_2022_market.py) | First 2022 group-stage backtest with real pre-kickoff odds. | offline |
| [`market_shadow_eval_2022.py`](market_shadow_eval_2022.py) | The read-only 2022 market study: B1, no-vig market and three predeclared fixed blends. | offline |
| [`test_beat_market.py`](test_beat_market.py), [`test_sharp_market.py`](test_sharp_market.py) | Exploratory analyses on auxiliary internationals. **Not tests.** See [below](#exploratory-analyses-that-are-not-tests). | offline |
| [`blend_variants.py`](blend_variants.py), [`diagnose_blend.py`](diagnose_blend.py), [`diagnose_sharp_alpha.py`](diagnose_sharp_alpha.py) | Follow-up diagnostics on the same auxiliary data. Same status: never confirmed. | offline |
| [`squad_feature_test.py`](squad_feature_test.py) | Transfermarkt starting-XI features vs Elo-only. Needs the optional `duckdb` extra. | offline |
| [`eval_player_plane_prematch.py`](eval_player_plane_prematch.py) | Does a starting-XI form signal add to Elo pre-match? LOCO logistic. | offline |

The 2022 study (48 matches) is single-tournament and the note itself calls its one significant blend
result "suggestive"; it selected no weight and promoted nothing
([`../notes/research/market_shadow_evaluation_2022.md`](../notes/research/market_shadow_evaluation_2022.md)).

**2026 forecasts and the tournament simulator**

| Script | What it does | Needs |
|---|---|---|
| [`forecast_runtime.py`](forecast_runtime.py) | Approved runtime forecast (B1 only); relabels the market blend as a shadow artifact. | offline |
| [`forecast_2026.py`](forecast_2026.py) | Forecasts remaining group matches and simulates advancement with frozen architectures. | offline |
| [`market_anchored_forecast.py`](market_anchored_forecast.py) | Combines the market consensus with the research forecast; records disagreements as falsifiable hypotheses. | offline |
| [`prequential_2026.py`](prequential_2026.py) | Walk-forward scorecard on finished 2026 group matches. **Fixed 2026-09-20 (E1).** | offline |
| [`validate_tournament_simulator.py`](validate_tournament_simulator.py) | Deterministic battery for the official 2026 tiebreak engine and group simulator. | offline, gate |
| [`audit_simulator_diff.py`](audit_simulator_diff.py) | Legacy vs official simulator on the same fixtures and seed, isolating the tiebreak-rule effect. | offline, report |
| [`validate_model_identity.py`](validate_model_identity.py) | Checks the canonical model identity and alias registry; never rewrites historical rows. | offline, gate |

## 4. Prospective 2026 shadow operations

24 files. This is the live experiment: predictions frozen before kickoff, scored after the final whistle,
compared with a no-vig bookmaker consensus. Runbooks:
[`PROSPECTIVE_COLLECTION_RUNBOOK`](../docs/PROSPECTIVE_COLLECTION_RUNBOOK.md),
[`SCORE_HARVEST_GUIDE`](../docs/SCORE_HARVEST_GUIDE.md),
[`WINDOWS_SCHEDULER_SETUP`](../docs/WINDOWS_SCHEDULER_SETUP.md),
[`CRON_SETUP`](../docs/CRON_SETUP.md).

```text
Collector (every 5 min):   windows/shadow_collector_cycle.py
                             -> fetch_odds_live_2026.py --execute     (only if a window is due and budget allows)
                             -> live_2026_shadow.py freeze            (immutable M1-M5 rows, append-only)
                             -> live_2026_shadow.py score             (never worked in production: E3)

Harvester (every 15 min):  run_prospective_score_harvester.py
                             -> refresh_prospective_final_results.py  (football-data.org only)
                             -> prospective_score_harvester_v1.py     (applies the snapshot rule; append-only)

On demand, in this order:  prospective_harvest/phase0_forensic_freeze.py   (hash the frozen inputs first)
                           audit_prospective_result_reconciliation.py      (gate)
                           select_primary_prospective_snapshots.py         (standalone registry for inspection)
                           prospective_benchmark_v1.py                     (metrics, CIs, decision ledger)
```

Verified outcome: 35 fixtures had frozen pre-kickoff predictions and 34 were scored (one was excluded
because it had no common market snapshot). The lab's own sample-size label for 34 fixtures is Tier C,
"exploratory". None of the reported paired comparisons has a 95% CI excluding zero, so there is no evidence
at this sample size that B1 or any blend differs from the market in either direction. Nothing was promoted.

**The market comparator is an early line, not a closing line.** For 31 of 34 fixtures the primary snapshot
is a baseline snapshot from the 2026-06-21 session, and across all 34 the median lead is about 98 hours
before kickoff. That is a direct consequence of E2, described
[at the end of this page](#two-scripts-fixed-on-2026-09-20). Reports:
[`PROSPECTIVE_MARKET_BENCHMARK_V1`](../notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md),
[`PROSPECTIVE_SHADOW_SCORECARD_V1`](../notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md).

**Collector side**

| Script | What it does | Needs |
|---|---|---|
| [`build_future_2026_queue.py`](build_future_2026_queue.py) | Queue of not-started fixtures with precomputed Elo anchors. Overwrites the tracked queue file (see entry point 6). | `API_FOOTBALL_KEY` |
| [`fetch_odds_live_2026.py`](fetch_odds_live_2026.py) | Budget-guarded snapshot: one batched h2h request, 500-credit ceiling, at least 10 minutes apart, fail-closed. Plans only unless `--execute`. | `ODDS_API_KEY`, 1 credit per `--execute` |
| [`live_2026_shadow.py`](live_2026_shadow.py) | `freeze` writes immutable M1–M5 predictions; `score` scores them. **Fixed 2026-09-20 (E2).** | offline |
| [`validate_shadow_integrity.py`](validate_shadow_integrity.py) | Integrity checks on the predictions file. | offline, gate |
| [`five_hour_supervisor.py`](five_hour_supervisor.py) | The one-off 2026-06-21 session: its own timed loop with `--hours`, `--max-credits`, `--dry-run`. Historical. | `ODDS_API_KEY`, `FOOTBALL_DATA_KEY` |
| [`shadow_session_close.py`](shadow_session_close.py) | Forensic close of that session; enforces snapshot time ≤ prediction time < kickoff. | offline |

**Score harvester (the only working scoring path)**

| Script | What it does | Needs |
|---|---|---|
| [`run_prospective_score_harvester.py`](run_prospective_score_harvester.py) | Bounded single cycle with a global lock, heartbeat, state file and JSONL log. | `FOOTBALL_DATA_KEY` while results are non-final |
| [`refresh_prospective_final_results.py`](refresh_prospective_final_results.py) | Resolves final results to canonical records; never overwrites the collector's file. | `FOOTBALL_DATA_KEY` (or `--offline`) |
| [`audit_prospective_result_reconciliation.py`](audit_prospective_result_reconciliation.py) | Reconciliation audit. | offline, gate |
| [`select_primary_prospective_snapshots.py`](select_primary_prospective_snapshots.py) | Latest common valid pre-kickoff snapshot per fixture. The rule is pre-specified and outcome-independent; its timing is self-attested in-repo, because the rule, the script and the results share one commit ([`pre-specification note`](../notes/research/prospective_score_harvest_preregistration.md)). | offline |
| [`prospective_score_harvester_v1.py`](prospective_score_harvester_v1.py) | The scorer. Writes only under `outputs/live_shadow/scoring_v1/`; corrections are appended, never edited. | offline |
| [`prospective_benchmark_v1.py`](prospective_benchmark_v1.py) | Metrics, 5000-resample match-level bootstrap, paired deltas, tier label, decision ledger. | offline |
| [`prospective_score_harvester_watchdog.py`](prospective_score_harvester_watchdog.py) | Restarts only a genuinely crashed scorer; never starts a second one; disables restart on an integrity failure. | offline |
| [`deploy_prospective_score_adapter.ps1`](deploy_prospective_score_adapter.ps1), [`rollback_prospective_score_adapter.ps1`](rollback_prospective_score_adapter.ps1) | Dry-run-by-default patch for the collector's own score step. **Deliberately never executed** (E3). Hard-coded path. | Windows |

**Earlier prospective machinery (kept as record)**

| Script | What it does | Needs |
|---|---|---|
| [`prospective_scorecard.py`](prospective_scorecard.py) | First append-only forecast ledger and scoring loop (2026-06-20). | `FOOTBALL_DATA_KEY` |
| [`prospective_market_scorecard.py`](prospective_market_scorecard.py) | Earlier deterministic market scorecard with the Tier A/B/C labels. Superseded by the harvester and benchmark. | offline |
| [`prospective_collect.py`](prospective_collect.py) | Collector for the frozen **in-play** model. Dry-run unless `--execute`. | `API_FOOTBALL_KEY` with `--execute` |
| [`prospective_score.py`](prospective_score.py) | Scores that in-play ledger for finished matches. | offline unless `--execute` |
| [`prospective_integrity_check.py`](prospective_integrity_check.py) | First-write-wins, labelling, point-in-time and schema checks on the in-play ledger. | offline, gate |
| [`run_prospective_collection.ps1`](run_prospective_collection.ps1), [`run_prospective_collection.sh`](run_prospective_collection.sh) | Single-pass wrappers for Task Scheduler and cron. Dry-run unless `EXECUTE=1`. Portable. | see above |
| [`install_windows_task_scheduler.ps1`](install_windows_task_scheduler.ps1), [`uninstall_windows_task_scheduler.ps1`](uninstall_windows_task_scheduler.ps1) | Register or remove the `WCDrawLab_ProspectiveCollector` task. Portable. | Windows |

No frozen in-play model was ever scored prospectively; its queue stayed pending. The in-play collector is
governance machinery, not an evaluated result.

## 5. In-play replay, evaluation and the holdout freeze

19 files. In-play models here forecast win/draw/loss from the current score and minute. Their names
(M0–M6) are a different namespace from the pre-match M1–M5.

```text
build_inplay_replay_2022 -> rebuild_replay_2022 / replay_quality_* -> build_inplay_state_2022
   -> evaluate_inplay_models_2022 (LOGO)             48 matches
build_multicomp_inplay   -> evaluate_inplay_multicomp (LOCO)          151 matches
build_statsbomb_inplay   -> extract_sb_intl_shots -> eval_nested_inplay (nested LOCO)   302 matches
eval_2026_holdout / eval_2026_recalibration -> freeze_final_holdout (v1) -> freeze_final_holdout_m2 (v2)
```

| Script | What it does | Needs |
|---|---|---|
| [`build_inplay_replay_2022.py`](build_inplay_replay_2022.py) | In-play replay table for the 2022 group stage; events are cached and never re-fetched. | `API_FOOTBALL_KEY` on a cold cache |
| [`rebuild_replay_2022.py`](rebuild_replay_2022.py) | Rebuilds the replay with provider-aware event semantics (the own-goal fix) and runs the 48-match reconciliation. | offline, report |
| [`replay_quality_2022.py`](replay_quality_2022.py), [`replay_2022_full_quality.py`](replay_2022_full_quality.py) | Replay data-quality tables; unavailable categories are classified, never inferred. | offline |
| [`build_inplay_state_2022.py`](build_inplay_state_2022.py), [`build_inplay_data_products_2022.py`](build_inplay_data_products_2022.py) | Canonical 2022 state dataset, data card, and split data products with a manifest. | offline |
| [`evaluate_inplay_models_2022.py`](evaluate_inplay_models_2022.py) | Leave-one-group-out evaluation with a match-level bootstrap. | offline |
| [`generate_inplay_research_predictions.py`](generate_inplay_research_predictions.py) | Out-of-fold predictions, every row labelled `research_only`. | offline |
| [`build_multicomp_inplay.py`](build_multicomp_inplay.py) | Fetches one competition's group-stage events (throttled, cached) and builds its state table. | `API_FOOTBALL_KEY`, `--max-events` |
| [`evaluate_inplay_multicomp.py`](evaluate_inplay_multicomp.py) | Leave-one-competition-out evaluation of M0/M1/M2/M5 across five tournaments. | offline |
| [`eval_inplay_xg.py`](eval_inplay_xg.py) | Does accumulated xG before the decision minute add to score and Elo? | offline |
| [`build_statsbomb_inplay.py`](build_statsbomb_inplay.py) | Downloads StatsBomb events for six men's international tournaments plus a bounded club sample. | net |
| [`extract_sb_intl_shots.py`](extract_sb_intl_shots.py) | Combined international shot table from the cache, for the xG feature families fixed before testing. | offline |
| [`eval_nested_inplay.py`](eval_nested_inplay.py) | Nested LOCO: model selection only in the inner loop; no 2026 match anywhere. | offline |
| [`eval_2026_holdout.py`](eval_2026_holdout.py), [`eval_2026_recalibration.py`](eval_2026_recalibration.py) | Fit on pre-2026 competitions, score 2026; temperature scaling. **See the caveat below.** | offline |
| [`freeze_final_holdout.py`](freeze_final_holdout.py) | Freeze v1 (`M2fit_temp`). Kept as an immutable record. | offline |
| [`freeze_final_holdout_m2.py`](freeze_final_holdout_m2.py) | Freeze v2: plain M2, the remaining-time Poisson with unfitted, hand-set constants (base rate 1.35, Elo coefficient 0.20). | offline |
| [`readiness_player_card_sub.py`](readiness_player_card_sub.py) | Measures data readiness for player, card and substitution models against fixed thresholds. | offline, report |

Caveat: model *parameters* were always train-only, but the "best" in-play model was chosen after repeated
views of 2026 results. The lab caught this itself, relabelled every affected claim
`invalid_due_to_model_selection_on_test_set` in
[`inplay_result_status_registry.yaml`](../notes/research/inplay_result_status_registry.yaml), and re-ran
selection with `eval_nested_inplay.py` on 302 StatsBomb men's internationals from six tournaments, with no
2026 data. The nested run never selected `M2fit_temp` or any xG variant: it chose plain M2 in 4 of 6 folds
and M5 in 2. Its gain over the fitted M1 baseline was not significant (dRPS −0.0042, 95% CI
[−0.0083, +0.0002]). That is why freeze v2 exists. See
[`inplay_evaluation_reconciliation.md`](../notes/research/inplay_evaluation_reconciliation.md) and
[`inplay_nested_evaluation.md`](../notes/research/inplay_nested_evaluation.md).

## 6. API-Football corpus, player history and player-impact evaluations

26 files. The discipline here is **predeclare, then pull**: a fixture manifest is committed using
metadata only, before any event or lineup is retrieved. All backfills are bounded, resumable and
append-only.

```text
api_football_empirical_audit -> api_football_acceptance_gate
api_football_corpus_predeclare (manifest committed first) -> api_football_corpus_backfill / _resume / _status
   -> api_football_data_quality_audit -> api_football_reconcile_events -> api_football_research_readiness
   -> build_api_football_historical_datasets
player_history_predeclare -> player_history_backfill / _resume / _status
   -> complete_full_player_history_backfill -> consolidate_and_verify_corpus -> audit_player_history_coverage
   -> build_player_history_features -> evaluate_player_impact_{wdl,next_goal,discipline}
```

| Script | What it does | Needs |
|---|---|---|
| [`api_football_empirical_audit.py`](api_football_empirical_audit.py) | Capability audit of the provider, hard-capped at 30 read-only requests. | `API_FOOTBALL_KEY`, spends on launch |
| [`api_football_acceptance_gate.py`](api_football_acceptance_gate.py) | Applies the provider acceptance protocol to the observed samples. | offline |
| [`api_football_historical_backfill.py`](api_football_historical_backfill.py), [`api_football_resume_backfill.py`](api_football_resume_backfill.py) | Pilot pull of events and lineups, hard cap 300 requests; stops on an auth or entitlement error. | `API_FOOTBALL_KEY`, spends on launch |
| [`api_football_corpus_predeclare.py`](api_football_corpus_predeclare.py) | Fixture manifest from metadata only (cohort, date order, league rotation). Fetches fixture lists. | `API_FOOTBALL_KEY` (budget 20) |
| [`api_football_corpus_backfill.py`](api_football_corpus_backfill.py), [`api_football_corpus_resume.py`](api_football_corpus_resume.py), [`api_football_corpus_status.py`](api_football_corpus_status.py) | Corpus pull; resume; counts-only status. | `API_FOOTBALL_KEY`, starts on launch, `--max-requests` default 1,800 (status is offline) |
| [`api_football_data_quality_audit.py`](api_football_data_quality_audit.py) | Real counts of events, cards, own goals, lineups, duplicates and completeness. | offline, report |
| [`api_football_reconcile_events.py`](api_football_reconcile_events.py) | Event-derived regulation score vs the provider's full-time score. | offline, report |
| [`api_football_research_readiness.py`](api_football_research_readiness.py) | Observed (not endpoint-implied) research-readiness counts. | offline, report |
| [`build_api_football_historical_datasets.py`](build_api_football_historical_datasets.py) | Causal research datasets; unresolved fixtures are excluded with a reason, never dropped silently. | offline |
| [`player_history_predeclare.py`](player_history_predeclare.py) | Stratified manifest by a fixed-seed fixture-ID hash, written before retrieval. | `API_FOOTBALL_KEY` (budget 30) |
| [`player_history_backfill.py`](player_history_backfill.py), [`player_history_resume.py`](player_history_resume.py), [`player_history_status.py`](player_history_status.py) | Events and lineups pull, at least 1 s per request, first write wins. | `API_FOOTBALL_KEY`, starts on launch, `--max-requests` default 1,800 (status is offline) |
| [`complete_full_player_history_backfill.py`](complete_full_player_history_backfill.py) | Completes the predeclared 2,000-fixture corpus into the canonical root. Probes `/status` first and keeps a reserve of at least 200 requests. | `API_FOOTBALL_KEY`, starts on launch, `--max-requests` default 5,000 |
| [`resume_full_player_history_backfill.py`](resume_full_player_history_backfill.py) | Daily resume: probes `/status` and continues only above a collector-aware quota reserve. | `API_FOOTBALL_KEY` |
| [`consolidate_and_verify_corpus.py`](consolidate_and_verify_corpus.py) | Copies prior pulls into the canonical root (no re-download) and writes `corpus_coverage_ledger.json`. | offline |
| [`audit_player_history_coverage.py`](audit_player_history_coverage.py) | Coverage and integrity of the corpus and derived priors. | offline, report |
| [`build_player_history_features.py`](build_player_history_features.py) | Rolling player-impact feature tables from raw events and lineups. | offline, hard-coded roots |
| [`evaluate_player_impact_wdl.py`](evaluate_player_impact_wdl.py), [`evaluate_player_impact_next_goal.py`](evaluate_player_impact_next_goal.py), [`evaluate_player_impact_discipline.py`](evaluate_player_impact_discipline.py) | LOCO evaluations with match-level bootstrap CIs. Nothing promoted. | offline |
| [`generate_provider_test_request.py`](generate_provider_test_request.py) | Vendor questionnaire mapped to the acceptance criteria; no credentials, nothing sent. | offline |
| [`run_provider_acceptance_tests.py`](run_provider_acceptance_tests.py) | Runs the acceptance protocol against a mock provider. | offline |

Two caveats. First, a backfill once reported 2,000/2,000 while only 1,940 fixtures were raw-backed in the
canonical root; the gate was changed to measure raw-backed coverage, and
[`corpus_coverage_ledger.json`](../data/reference/corpus_coverage_ledger.json) is the current source of
truth. Second, the reconciliation result (event-derived regulation scores matched the provider's full-time
score on all 900 audited fixtures, then on 1,120 of 1,120 after a predeclared 220-fixture extension) covers
only those audited fixtures. It is not claimed for the full 2,000-fixture pull.

## 7. StatsBomb bridge, xG state and the dynamic in-play panel

13 files. These join API-Football fixtures to StatsBomb open-data events by an exact match bridge, then
build causal xG features (only events at or before each snapshot minute).

```text
build_api_statsbomb_match_bridge -> build_xg_event_state_features
complete_statsbomb_event_cache -> audit_statsbomb_event_cache
   -> join_complete_xg_into_dynamic_snapshots -> audit_complete_xg_snapshot_join
build_dynamic_inplay_panel + build_dynamic_temporal_player_priors + build_dynamic_xg_state
   -> model_jobs/ (section 13)
```

| Script | What it does | Needs |
|---|---|---|
| [`build_research_truth_registry.py`](build_research_truth_registry.py) | Scans actual raw data across worktrees to resolve conflicting coverage claims, rather than trusting summaries. | offline, hard-coded roots |
| [`validate_research_asset_paths.py`](validate_research_asset_paths.py) | Data-root registry check: roots resolve, forbidden roots excluded, raw stays gitignored. | offline, gate |
| [`build_api_statsbomb_match_bridge.py`](build_api_statsbomb_match_bridge.py) | 1:1 links only when competition, season, both teams, kickoff date and final score all agree exactly and the match is unambiguous. No fuzzy name linking. | offline |
| [`build_xg_event_state_features.py`](build_xg_event_state_features.py) | Causal xG event-state features on a fixed decision grid. | offline |
| [`complete_statsbomb_event_cache.py`](complete_statsbomb_event_cache.py) | Fetches missing exact-bridge event files from the official StatsBomb open-data source only. | net |
| [`audit_statsbomb_event_cache.py`](audit_statsbomb_event_cache.py) | Counts *valid* exact-bridge files. A file existing is not enough. | offline, report |
| [`join_complete_xg_into_dynamic_snapshots.py`](join_complete_xg_into_dynamic_snapshots.py) | The xG-to-snapshot join for exact-bridged internationals. | offline |
| [`audit_complete_xg_snapshot_join.py`](audit_complete_xg_snapshot_join.py) | The join is non-empty, regulation-only, exact-bridge-only. | offline, gate |
| [`build_dynamic_inplay_panel.py`](build_dynamic_inplay_panel.py) | Canonical dynamic in-play panel from the full corpus. | offline |
| [`build_dynamic_temporal_player_priors.py`](build_dynamic_temporal_player_priors.py), [`audit_dynamic_player_priors.py`](audit_dynamic_player_priors.py) | Temporal player priors; the audit runs synthetic self-tests for future-appearance leakage, then checks the real outputs. | offline; audit is a gate |
| [`build_dynamic_xg_state.py`](build_dynamic_xg_state.py), [`audit_dynamic_xg_state.py`](audit_dynamic_xg_state.py) | Dynamic xG state; the audit includes a synthetic "no future xG" self-test. | offline; audit is a gate |

## 8. Event-process, residual-intensity and evidence-power builders

12 files. These are the top-level builders and audits that the `event_process_jobs/`, `residual_jobs/`
and `evidence_jobs/` queues call.

| Script | What it does | Needs |
|---|---|---|
| [`build_statsbomb_event_process_catalog.py`](build_statsbomb_event_process_catalog.py) | Inventory of the approved StatsBomb open catalogue (men's competitions). | net |
| [`build_event_process_auxiliary_manifest.py`](build_event_process_auxiliary_manifest.py) | Deterministic club-only auxiliary manifest; selection never uses results. | offline |
| [`acquire_event_process_auxiliary.py`](acquire_event_process_auxiliary.py) | Pulls the manifested club event files with hash validation and full provenance. | net |
| [`build_event_process_snapshots.py`](build_event_process_snapshots.py) | Event-process snapshot datasets and their target and quality side-tables. | offline |
| [`build_residual_goal_intensity_dataset.py`](build_residual_goal_intensity_dataset.py), [`audit_residual_goal_intensity_dataset.py`](audit_residual_goal_intensity_dataset.py) | Residual goal-intensity dataset and horizon targets; the audit re-checks every schema invariant on the produced files. | offline; audit is a gate |
| [`build_research_evidence_registry.py`](build_research_evidence_registry.py) | One row per major artifact across prior research programmes, with a status such as `contradicted`. | offline |
| [`build_evaluation_cohort_lineage.py`](build_evaluation_cohort_lineage.py), [`audit_evaluation_cohort_lineage.py`](audit_evaluation_cohort_lineage.py) | One row per fixture with explicit stage columns and drop reasons; the audit re-derives the funnel counts from the source files and compares them. | offline; audit is a gate |
| [`audit_residual_58_match_cohort.py`](audit_residual_58_match_cohort.py) | From-scratch reconstruction of the 58-match cohort and its reference metrics. Standard library only; does not import `wcdrawlab`. | offline, report |
| [`run_match_level_power_analysis.py`](run_match_level_power_analysis.py) | Match-clustered power analysis on the 58-match cohort. **Superseded** by the 231-match analysis in section 9. | offline |
| [`build_live_readiness_matrix.py`](build_live_readiness_matrix.py) | Classifies about 20 in-play feature families by how close each is to point-in-time use. | offline |

## 9. International Event Lake

13 files. A content-addressed, append-only store of StatsBomb Open Data event files for senior men's
internationals. It lives **outside the repository** on the author's disk and is not redistributed; the
repo tracks only manifests and audits. Runbook:
[`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_RUNBOOK`](../docs/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_RUNBOOK.md).

```text
init -> build_official_modern_international_catalog -> build_legacy_..._restoration_manifest -> restore
     -> bridge_official_international_matches -> acquire_official_international_events
     -> build_..._manifest -> audit_international_event_lake / audit_official_... / verify_..._retention
     -> build_international_event_lake_cohort -> run_..._power_analysis -> rerun_..._models
```

| Script | What it does | Needs |
|---|---|---|
| [`init_international_event_lake.py`](init_international_event_lake.py) | Creates the lake tree idempotently and verifies it is outside every git worktree. Never deletes. | offline |
| [`build_official_modern_international_catalog.py`](build_official_modern_international_catalog.py) | Official catalogue and match lists for the allowed competitions. | net |
| [`build_legacy_international_bridge_restoration_manifest.py`](build_legacy_international_bridge_restoration_manifest.py) | Per-row restoration manifest for the legacy exact bridge. | offline |
| [`restore_international_event_lake.py`](restore_international_event_lake.py) | Copies valid, hash-verified local files into the lake. | offline |
| [`bridge_official_international_matches.py`](bridge_official_international_matches.py) | Strict exact bridge from catalogue matches to local fixtures; ambiguous rows are dropped, never guessed. | offline |
| [`acquire_official_international_events.py`](acquire_official_international_events.py) | Brings missing or invalid event files into the lake, local copy first, official source second. | net |
| [`build_international_event_lake_manifest.py`](build_international_event_lake_manifest.py) | Rebuilds the index from the immutable manifest, then runs the sentinel. | offline |
| [`audit_international_event_lake.py`](audit_international_event_lake.py) | Fail-closed sentinel over every object: present, hash matches, valid JSON, resolves to one bridge row. | offline, gate |
| [`audit_official_international_events.py`](audit_official_international_events.py) | Sentinel plus a coverage cross-check against the legacy and modern bridges. | offline, gate |
| [`verify_international_event_lake_retention.py`](verify_international_event_lake_retention.py) | No valid object was dropped or orphaned; the index is a subset of manifest history. | offline, gate |
| [`build_international_event_lake_cohort.py`](build_international_event_lake_cohort.py) | The single frozen evaluation cohort and its exclusion ledger. | offline, hard-coded roots |
| [`run_international_event_lake_power_analysis.py`](run_international_event_lake_power_analysis.py) | Match-level power on the 231-match cohort. The match, not the snapshot, is the independent unit. | offline |
| [`rerun_international_event_lake_models.py`](rerun_international_event_lake_models.py) | Reruns the already-specified model families on the frozen cohort. No new features or search. | offline |

Verified outcome: power for a 0.005 absolute RPS gain is only 0.28 at 231 matches, and 80% power first
appears at the roughly 1,200-match grid point
([`power analysis`](../data/reference/international_event_lake_power_analysis.md)). On the rerun no
candidate cleared the locked multi-rule gate; all ten models stayed `reference_only` (ERRATA E6 explains
the two vocabularies used for that outcome).

## 10. Hierarchical club-to-international transfer

6 files. **Status: incomplete / null.** No model improved on the reference T0, the run had zero club
training rows so cross-domain lift is *untested*, and the decision ledger was cleared during an unfinished
repair and never regenerated (ERRATA E5). There is no git tag for this line.

| Script | What it does | Needs |
|---|---|---|
| [`build_domain_event_process_inventory.py`](build_domain_event_process_inventory.py) | Per-match inventory of event-process completeness across the international and club domains. | offline, hard-coded roots |
| [`audit_domain_feature_overlap.py`](audit_domain_feature_overlap.py) | Feature-overlap and domain-shift audit per feature family. | offline, report |
| [`build_domain_normalized_transfer_dataset.py`](build_domain_normalized_transfer_dataset.py), [`audit_domain_normalized_transfer_dataset.py`](audit_domain_normalized_transfer_dataset.py) | Domain-normalised transfer dataset; the audit re-asserts every leakage invariant. | offline; audit is a gate |
| [`run_hierarchical_transfer_eval.py`](run_hierarchical_transfer_eval.py) | The T0–T7 ladder evaluation with the pre-specified ablations. | offline |
| [`hierarchical_transfer_gatekeeper.py`](hierarchical_transfer_gatekeeper.py) | Checks that the event-lake dependency is finished, tagged and reported. If so, and the `WorldCupHierarchicalDomainTransferRun` task is registered, it starts that task once; otherwise it only logs. | offline, Windows, hard-coded paths |

## 11. Commentary NLP (SoccerNet, club football)

23 files. A side line on **European club football**, not the World Cup. It asks whether automatic speech
recognition commentary can produce reliable "silver" event labels, meaning machine-generated labels
accepted only if they pass a precision gate. Under the gate fixed in advance (at least 50 emissions and a
Wilson 95% lower bound on precision of at least 0.80, plus timing and fold stability), **0 of 12 event
classes qualified** and the silver-label dataset was released empty. No outcome model was trained and no
predictive value is claimed.
The repository tracks no commentary text and no SoccerNet label files, only manifests and aggregates.

```text
build_commentary_catalog -> commentary_sample_acquire / commentary_acquire_soccernet_real -> commentary_normalize
acquire_soccernet_action_labels -> verify_soccernet_action_labels -> build_soccernet_overlap_manifest
   -> run_soccernet_alignment / run_soccernet_folds -> build_soccernet_weak_supervision_dataset
   -> train_commentary_precision_models -> evaluate_commentary_precision_models (LOCO)
   -> apply_commentary_silver_gate -> generate_soccernet_silver_labels -> build_soccernet_silver_label_release
validate_commentary_live_eligibility      (separate fail-closed gate for live use)
```

| Script | What it does | Needs |
|---|---|---|
| [`build_commentary_catalog.py`](build_commentary_catalog.py) | Source catalogue; counts are marked verified or unverified, never invented. | offline |
| [`commentary_sample_acquire.py`](commentary_sample_acquire.py) | Downloads only sources classified as open for research; dry-run by default. | net |
| [`commentary_acquire_soccernet_real.py`](commentary_acquire_soccernet_real.py) | Bounded SoccerNet-Echoes sample (at most 10 games) via `huggingface_hub`. | net, `commentary` extra |
| [`acquire_soccernet_action_labels.py`](acquire_soccernet_action_labels.py), [`verify_soccernet_action_labels.py`](verify_soccernet_action_labels.py) | Action-spotting labels via the official SoccerNet package; no videos, no password; then counts and checksums. | net, `commentary` extra; verify is a report |
| [`commentary_normalize.py`](commentary_normalize.py), [`commentary_source_quality_audit.py`](commentary_source_quality_audit.py), [`commentary_event_taxonomy_eval.py`](commentary_event_taxonomy_eval.py) | Normalise a sample to the canonical contract; summarise timing, language and duplicates; check taxonomy coverage. | offline |
| [`commentary_alignment_audit.py`](commentary_alignment_audit.py) | Alignment audit that runs on synthetic data when no permitted real sample exists. | offline, report |
| [`build_soccernet_overlap_manifest.py`](build_soccernet_overlap_manifest.py), [`audit_soccernet_commentary_label_quality.py`](audit_soccernet_commentary_label_quality.py) | Real overlap between commentary games and label games; quality audit with counts and rates only. | offline |
| [`run_soccernet_alignment.py`](run_soccernet_alignment.py), [`run_soccernet_folds.py`](run_soccernet_folds.py), [`audit_soccernet_alignment.py`](audit_soccernet_alignment.py) | Match-level-split alignment evaluation; the six-fold LOCO table and the language-variant comparison; a read-only audit of both. | offline |
| [`build_soccernet_weak_supervision_dataset.py`](build_soccernet_weak_supervision_dataset.py) | Derived dataset with content hashes instead of text. | offline |
| [`train_commentary_precision_models.py`](train_commentary_precision_models.py), [`evaluate_commentary_precision_models.py`](evaluate_commentary_precision_models.py) | Precision ladder; all fitting and threshold selection on training competitions only. | offline |
| [`apply_commentary_silver_gate.py`](apply_commentary_silver_gate.py) | Applies the frozen gate to per-class metrics and writes the decision. | offline |
| [`generate_soccernet_silver_labels.py`](generate_soccernet_silver_labels.py), [`build_soccernet_silver_label_release.py`](build_soccernet_silver_label_release.py) | Silver-label emission and packaging for approved classes only (there were none). | offline |
| [`evaluate_commentary_coverage_recovery.py`](evaluate_commentary_coverage_recovery.py) | Masking experiment: can silver labels recover hidden events? | offline |
| [`build_commentary_low_confidence_signals.py`](build_commentary_low_confidence_signals.py) | Flagged low-confidence signals for corner, foul and yellow card. Explicitly not silver labels and not ground truth. | offline |
| [`validate_commentary_live_eligibility.py`](validate_commentary_live_eligibility.py) | Fails if any source is wrongly marked live-eligible. With current sources none qualifies. | offline, gate |

## 12. Supervisors, watchdogs and run launchers

15 files. One generic controller runs every job queue in section 13.

[`deep_research_supervisor.py`](deep_research_supervisor.py) reads a YAML config from
[`../configs/`](../configs/) that lists an ordered, finite job queue. Before each job it checks a hard
deadline, an API-request budget and the shadow collector's heartbeat, and it stops rather than continue if
any check fails. Each job is invoked as `python <script> --run-dir <dir>` and must print a JSON status
object as its last line. State is checkpointed atomically after every job, so re-running with
`--resume-run-id` skips completed jobs. `--dry-run` runs no job; it only checks that every script in the
queue exists. Runbook: [`DEEP_RESEARCH_CONTROLLER_RUNBOOK`](../docs/DEEP_RESEARCH_CONTROLLER_RUNBOOK.md).

> [!NOTE]
> The controller code is portable, but every shipped queue config sets `collector_heartbeat` to a file in
> the author's collector checkout. The health check runs before each job, including under `--dry-run`, so
> on any other machine (or with no collector running) the controller blocks the whole queue with
> `collector heartbeat missing` until you point that setting at a fresh heartbeat file of your own.

| Script | What it does |
|---|---|
| [`deep_research_supervisor.py`](deep_research_supervisor.py) | The controller described above. Portable code; see the note above about the shipped configs. |
| [`deep_research_worker.py`](deep_research_worker.py) | Runs a single job script and relays its JSON result. Portable. |
| [`research_truth_fusion_watchdog.py`](research_truth_fusion_watchdog.py) | 15-minute watchdog for the research-truth run. |
| [`research_evidence_watchdog.py`](research_evidence_watchdog.py) | 10-minute watchdog for the evidence-power run. |
| [`international_event_lake_watchdog.py`](international_event_lake_watchdog.py) | 10-minute watchdog for the event-lake run. |
| [`hierarchical_domain_transfer_watchdog.py`](hierarchical_domain_transfer_watchdog.py) | 10-minute watchdog for the transfer run. |
| [`run_deep_research_night.ps1`](run_deep_research_night.ps1) | Launcher: `deep_research_run_v1.yaml`, 4 hours. |
| [`run_player_impact_night.ps1`](run_player_impact_night.ps1) | Launcher: `player_impact_xg_fusion_run_v1.yaml`, 6 hours. |
| [`run_research_truth_full_corpus_xg_fusion.ps1`](run_research_truth_full_corpus_xg_fusion.ps1) | Launcher: `research_truth_full_corpus_xg_fusion_run_v1.yaml`, 10 hours, at most 2,000 API requests. |
| [`run_dynamic_inplay_modeling_phase.ps1`](run_dynamic_inplay_modeling_phase.ps1) | Launcher: `dynamic_inplay_modeling_phase_v1.yaml`, 8 hours; has `-DryRun`. Resolves its own root. |
| [`run_event_process_intelligence.ps1`](run_event_process_intelligence.ps1) | Launcher: `event_process_intelligence_v1.yaml`, 10 hours. |
| [`run_residual_goal_intensity_v1.ps1`](run_residual_goal_intensity_v1.ps1) | Launcher: `residual_goal_intensity_v1.yaml`, 8 hours. |
| [`run_evidence_power_consolidation_v1.ps1`](run_evidence_power_consolidation_v1.ps1) | Launcher: `evidence_power_consolidation_v1.yaml`, 8 hours. |
| [`run_international_event_lake_restoration.ps1`](run_international_event_lake_restoration.ps1) | Launcher: `international_event_lake_restoration_v1.yaml`, 10 hours. |
| [`run_hierarchical_domain_transfer_v1.ps1`](run_hierarchical_domain_transfer_v1.ps1) | Launcher: `hierarchical_domain_transfer_v1.yaml`, 10 hours. |

Each watchdog holds one global lock, never starts a second worker, and never touches the
`WorldCupShadowCollector` task. The four watchdogs and eight of the nine launchers hard-code the author's
worktree paths (E7). These were bounded, unattended runs on one machine. Treat the launchers as a log of
what was run, not as commands to copy.

## 13. Staged job queues (seven subfolders)

128 files. Each queue follows the same staged shape, so a run can stop and resume at any job:

```text
preflight -> dataset / snapshots -> audits -> fit -> forward-chain eval (primary) -> LOCO eval (secondary)
          -> ablations -> calibration + match-level bootstrap -> failure analysis
          -> decision ledger / model registry -> report + integrity audit
```

Many jobs are thin wrappers around the top-level builders and audits in sections 6 to 10; the evaluation
jobs do their own fitting and scoring through the queue's shared helper. Every job records evidence in the
run directory and emits one JSON status line. Decision-ledger words (`reference_only`,
`rejected`, `data_insufficient`, ...) are defined in [`../docs/GLOSSARY.md`](../docs/GLOSSARY.md).

| Folder | Files | Naming pattern | Supervisor config | Spends quota? | Outcome |
|---|---|---|---|---|---|
| [`research_jobs/`](research_jobs/) | 36 | `job01`–`job11` (11), `pi_job01`–`pi_job13` (13), `rt_job01`–`rt_job09` (9), helpers `_common.py`, `_job.py`, `_models.py` | see below | yes, three jobs | see below |
| [`model_jobs/`](model_jobs/) | 17 | `mj_job01_preflight` … `mj_job16_report_completion`, helper `_mj_common.py` | `dynamic_inplay_modeling_phase_v1.yaml` | no (offline; budget capped at 1) | 0 candidates promoted |
| [`event_process_jobs/`](event_process_jobs/) | 18 | `ep_job01_preflight` … `ep_job16_catalog_ledger_report`, helpers `_ep.py`, `_ep_lib.py` | `event_process_intelligence_v1.yaml` | no; `ep_job04` downloads open data, and `ep_job02` does too if the tracked catalogue file is absent | 20 `reference_only`, 2 `data_insufficient`, 0 candidates |
| [`residual_jobs/`](residual_jobs/) | 15 | `rg_job01_preflight` … `rg_job14_report_integrity`, helper `_rg.py` | `residual_goal_intensity_v1.yaml` | no | 7 `reference_only`, 6 `rejected`, 3 `data_insufficient`, 0 candidates |
| [`evidence_jobs/`](evidence_jobs/) | 13 | `ev_job01_preflight` … `ev_job12_final_report`, helper `_ev.py` | `evidence_power_consolidation_v1.yaml` | no | audit and power analysis; no model claims |
| [`lake_jobs/`](lake_jobs/) | 14 | `lk_job01_preflight` … `lk_job13_completion_report`, helper `_lk.py` | `international_event_lake_restoration_v1.yaml` | no; `lk_job03` and `lk_job06` download open data | 10 `reference_only`, 0 candidates |
| [`ht_jobs/`](ht_jobs/) | 15 | `ht_job01_preflight` … `ht_job14_report_integrity`, helper `_ht.py` | `hierarchical_domain_transfer_v1.yaml` | no | incomplete / null; ledger missing (E5) |

`research_jobs/` holds three separate queues that share helpers:

| Prefix | Run | Config | Completion note | Notes |
|---|---|---|---|---|
| `job*` | Deep-research in-play foundation | `deep_research_run_v1.yaml` (4 h, at most 600 API requests) | [`DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION`](../notes/research/DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION.md) | `job02_extension_backfill.py` calls API-Football. Team-state and lineup-continuity models showed no evidence of improvement over the remaining-time Poisson reference on 627 internationals. |
| `pi_job*` | Player-impact and xG fusion | `player_impact_xg_fusion_run_v1.yaml` (6 h, at most 3,500 API requests) | [`PLAYER_IMPACT_XG_FUSION_COMPLETION`](../notes/research/PLAYER_IMPACT_XG_FUSION_COMPLETION.md) | `pi_job03_backfill.py` calls API-Football and skips if the key is missing. The first sprint's P1–P4 table was identical to the prior sprint's and was later downgraded to incomplete; the valid full-corpus rerun promoted nothing. |
| `rt_job*` | Research-truth full-corpus xG fusion | `research_truth_full_corpus_xg_fusion_run_v1.yaml` (10 h) | [`RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION`](../notes/research/RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION.md) | `rt_job02_corpus.py` runs the player-history backfill (API-Football). `rt_job04_statsbomb.py` downloads StatsBomb open data (no key). The launcher caps the run at 2,000 API requests. The sprint's git tag is literally `research-truth-full-corpus-xg-fusion-incomplete`. |

Completion notes for the other queues:
[`DYNAMIC_INPLAY_MODELING_PHASE_V1`](../notes/research/DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md),
[`EVENT_PROCESS_INTELLIGENCE_V1`](../notes/research/EVENT_PROCESS_INTELLIGENCE_V1_COMPLETION.md),
[`RESIDUAL_GOAL_INTENSITY_V1`](../notes/research/RESIDUAL_GOAL_INTENSITY_V1_COMPLETION.md),
[`EVIDENCE_POWER_CONSOLIDATION_V1`](../notes/research/EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md),
[`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1`](../notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md),
[`HIERARCHICAL_DOMAIN_TRANSFER_V1`](../notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md).

The per-queue helpers (`_common.py`, `_mj_common.py`, `_ep_lib.py`, `_rg.py`, `_ev.py`, `_lk.py`, `_ht.py`)
resolve the run directory and data roots. `research_jobs/_common.py`, `_ev.py`, `_lk.py` and `_ht.py`
contain absolute paths directly; the others go through the roots configs. Most helpers also refuse to run
from, or read from, the collector checkout, and `_ev.py`, `_lk.py` and `_ht.py` list forbidden import tokens
(network libraries, provider, odds and live-collector modules). Each of those queues scans its own job
files for the tokens in its preflight job; the evidence and event-lake queues are also scanned by the test
suite.

## 14. `prospective_harvest/` and `windows/`

**[`prospective_harvest/`](prospective_harvest/)** holds 2 files: the score harvester's internals.

| Script | What it does |
|---|---|
| [`prospective_harvest/_harvest_common.py`](prospective_harvest/_harvest_common.py) | Paths and helpers. Reads the collector's immutable inputs and writes only under `outputs/live_shadow/scoring_v1/`. Set `PSH_COLLECTOR_ROOT` when the collector runs in a different checkout; otherwise it defaults to this repo. |
| [`prospective_harvest/phase0_forensic_freeze.py`](prospective_harvest/phase0_forensic_freeze.py) | Hashes the frozen inputs and records counts before any scoring (680 prediction rows, 35 fixtures). Its tracked output still shows the original machine's paths. |

**[`windows/`](windows/)** holds 34 files: 1 Python entry point, 3 `run_*.ps1` wrappers, 15
`install_*.ps1` and 15 matching `uninstall_*.ps1`. Every task runs a bounded single pass; none is a
daemon. Setup guide: [`WINDOWS_SCHEDULER_SETUP`](../docs/WINDOWS_SCHEDULER_SETUP.md).

| Pattern | Count | What it does | Portable? |
|---|---|---|---|
| `shadow_collector_cycle.py` | 1 | The collector cycle (section 4). | yes |
| `run_shadow_collector.ps1`, `run_prospective_score_harvester.ps1`, `run_prospective_score_harvester_watchdog.ps1` | 3 | Wrappers Task Scheduler calls: prefer the project venv, log to `outputs/`, run one cycle, return its exit code. | yes |
| `install_shadow_collector_task.ps1` / `uninstall_…` | 2 | `WorldCupShadowCollector`, every 5 minutes until a hard end date (`-HardEndUtc`, default 2026-07-05, now past). | yes |
| `install_prospective_score_harvester_tasks.ps1` / `uninstall_…` | 2 | `WorldCupProspectiveScoreHarvester` and its `…Watchdog`, every 15 minutes. | yes |
| `install_<research_run>_task.ps1` / `uninstall_…` | 16 | One-time bounded research runs: deep-research night, player impact, research-truth fusion, event-process, residual goal intensity, evidence-power, event lake, hierarchical transfer. | installers no (E7) |
| `install_<run>_watchdog_task.ps1` / `uninstall_…` | 8 | Watchdogs for research-truth (15 min), evidence-power, event lake and hierarchical transfer (10 min). | installers no (E7) |
| `install_research_truth_resume_task.ps1` / `uninstall_…` | 2 | Daily off-peak quota-aware resume of the player-history backfill. | installer no (E7) |

The uninstallers only need the task name, so they work anywhere.

To stop everything registered from `windows/`:

```powershell
Get-ScheduledTask | Where-Object { $_.TaskName -like 'WorldCup*' } | Disable-ScheduledTask
```

Disabling deletes nothing. The older in-play collector task from section 4 uses a different name,
`WCDrawLab_ProspectiveCollector`; remove it with
[`uninstall_windows_task_scheduler.ps1`](uninstall_windows_task_scheduler.ps1).

## 15. Repository hygiene

3 files from the research period, plus the figure script added for the public release.

| Script | What it does | Needs |
|---|---|---|
| [`check_secret_hygiene.py`](check_secret_hygiene.py) | Exit 1 if `.env.example` contains anything that looks like a real credential. | offline, gate |
| [`migrate_secrets_to_env.py`](migrate_secrets_to_env.py) | Moves real values out of `.env.example` into a gitignored `.env`. **Edits both files.** Prints names only. | offline |
| [`run_data_integration_tests.py`](run_data_integration_tests.py) | Runs the data-dependent integration tests that a clean clone skips; returns pytest's exit code. See [`TESTING_AND_DATA_DEPENDENCIES`](../docs/TESTING_AND_DATA_DEPENDENCIES.md). | offline (needs gitignored data) |
| [`make_readme_figures.py`](make_readme_figures.py) | Redraws the two SVG figures in `docs/img/` from committed files only. Standard library, deterministic output. Fits, tunes and re-scores nothing. `--check` exits 1 if the committed SVGs are out of date. | offline; gate with `--check` |

---

## Read-only audits: which ones gate and which ones only report

Verified by reading each script's exit path. "Gate" means a non-zero exit code on violation, so the script
can stop a pipeline or a CI job. "Report" means it writes or prints findings and exits 0.

**Gates (18)**

| Area | Scripts |
|---|---|
| Secrets and identity | `check_secret_hygiene.py`, `validate_model_identity.py`, `validate_research_asset_paths.py` |
| Simulator | `validate_tournament_simulator.py` |
| Prospective ledgers | `validate_shadow_integrity.py`, `prospective_integrity_check.py`, `audit_prospective_result_reconciliation.py` (exit 2) |
| Event lake | `audit_international_event_lake.py`, `audit_official_international_events.py`, `verify_international_event_lake_retention.py` |
| Datasets | `audit_evaluation_cohort_lineage.py`, `audit_residual_goal_intensity_dataset.py`, `audit_domain_normalized_transfer_dataset.py`, `audit_dynamic_player_priors.py`, `audit_dynamic_xg_state.py`, `audit_complete_xg_snapshot_join.py` |
| Commentary | `validate_commentary_live_eligibility.py` |
| Tests | `run_data_integration_tests.py` (pytest's code) |

**Reports (exit 0 either way)**

`audit_public_data.py`, `audit_simulator_diff.py`, `audit_player_history_coverage.py`,
`audit_statsbomb_event_cache.py`, `audit_residual_58_match_cohort.py`, `audit_domain_feature_overlap.py`,
`audit_soccernet_alignment.py`, `audit_soccernet_commentary_label_quality.py`,
`verify_soccernet_action_labels.py`, `validate_odds_pilot_2022.py`, `rebuild_replay_2022.py`,
`commentary_alignment_audit.py`, `api_football_data_quality_audit.py`, `api_football_reconcile_events.py`
and `api_football_research_readiness.py`.

These are internal checks written by the same project. None is a third-party review.

## Exploratory analyses that are not tests

[`test_beat_market.py`](test_beat_market.py), [`test_sharp_market.py`](test_sharp_market.py) and
[`squad_feature_test.py`](squad_feature_test.py) are **exploratory analyses, not tests**. They have no
`test_` functions, and pytest collects only `tests/` (`testpaths = tests` in
[`../pytest.ini`](../pytest.ini)). The filenames are historical and were left unchanged.

The first two asked, on 253–341 auxiliary internationals from 2020–2025, whether a model or a fixed blend
could score better than the bookmaker consensus. The early notes that answered yes reported point
estimates on 3 of 4 folds with no confidence intervals. The lab later reclassified them as auxiliary, and
they were never confirmed prospectively (ERRATA E4). This repository does not stand behind that claim.
What the later, better-controlled evidence shows:

- the Tier-2 gate (144 pooled dev matches) found no evidence that any baseline improves on plain Elo;
- the 2022 retrospective study (48 matches) is single-tournament, applied no multiplicity correction, and
  its own note calls its one significant blend result "suggestive";
- in the 2026 prospective benchmark (34 scored fixtures, **early-line** market comparator, not a closing
  line) no reported paired comparison between any model and the market had a 95% CI excluding zero.

`blend_variants.py`, `diagnose_blend.py` and `diagnose_sharp_alpha.py` are follow-ups on the same
auxiliary data and share that status. Their docstrings keep the language of the day; read them as
hypotheses that were not confirmed.

`squad_feature_test.py` tested Transfermarkt starting-XI value, age and league-share features on 128 Copa
América, AFCON and Asian Cup games. Five-fold CV log-loss was 0.834 with the features against 0.813 for
Elo only, so the features were rejected. It needs the optional `duckdb` extra (`pip install -e ".[data]"`).

## Two scripts fixed on 2026-09-20

Both defects were found by the read-only audit that prepared this repository for release. Details and
evidence are in [`../docs/ERRATA.md`](../docs/ERRATA.md).

| Script | Erratum | What was wrong | What changed |
|---|---|---|---|
| [`prequential_2026.py`](prequential_2026.py) | **E1** | The candidate's one-row test frame was built with `m.to_frame().T`, which makes every column `object` dtype. The leakage guard then kept zero numeric columns, every feature was zero-filled, and V8 produced near-constant forecasts. The recorded "V8 worse than B1 on 2026" comparison was an artifact. | The row is now built with its dtypes preserved. On the same 33 matches V8 and B1 are tied (RPS 0.173 vs 0.174, log-loss 0.948 vs 0.958). B1's figures were never affected. V8 stays shadow-only for the valid reason: no significant dev-fold improvement. |
| [`live_2026_shadow.py`](live_2026_shadow.py) | **E2** | [`fetch_odds_live_2026.py`](fetch_odds_live_2026.py) wrote its payload under `"events"`; the freezer read only `"data"`. All 47 snapshots from the durable collector were silently ignored, so every market-bearing prediction came from the 9 snapshots of the 2026-06-21 session. | The freezer now accepts both keys. **The historical ledger is unchanged**, which is why the benchmark's market comparator is an early line and must be read that way. |

A third known defect was left in place on purpose: the collector's own `score` step never worked in
production (E3). The separate score harvester in section 4 is the only working scoring path.
