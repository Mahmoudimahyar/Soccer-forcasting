# `data/reference/` — ledgers, manifests and audits

This folder is the lab's machine-readable record: **88 tracked files** (JSON, CSV, two Markdown reports,
one YAML; the largest is about 1.9 MB) that state *what was decided, on which matches, from which inputs,
and why*. When a note or the top-level README cites a verdict, a cohort or a manifest, this is where you
check it.

Everything here is research-only and paper-only. Nothing in this folder is betting or financial advice,
and no file records a trade, because no order was ever placed.

**Contents**

1. [What lives here, and why it is tracked while the raw data is not](#1-what-lives-here-and-why-it-is-tracked-while-the-raw-data-is-not)
2. [Decision vocabulary](#2-decision-vocabulary)
3. [Index by family](#3-index-by-family)
4. [Read this before trusting a number](#4-read-this-before-trusting-a-number)
5. [Loading a ledger](#5-loading-a-ledger)

If you read only one section, read [section 4](#4-read-this-before-trusting-a-number).

---

## 1. What lives here, and why it is tracked while the raw data is not

**The raw data is not in this repository.** Provider payloads and derived tables live under `data/raw/`,
`data/processed/`, `data/cache/` and `outputs/`, all of which are gitignored (one metadata-only file,
`data/processed/source_provenance.json`, is tracked on purpose). The StatsBomb event lake
lives on the author's disk, outside the repository, and is not redistributed. The reasons are third-party
licence terms, size, and the fact that most sources need your own API key and quota.

**What is tracked here is either produced by the lab or limited to identifiers and match-listing fields
from third-party sources** (see [4e](#note-e)):

- decision ledgers (one verdict per model, per research line);
- cohort lineage (which matches went in, which were dropped, and the reason for every drop);
- power analyses (how many matches a given improvement would need to be detectable);
- manifests of fixture identifiers and content hashes;
- audits and registries that re-check earlier claims;
- desk-research catalogs of data providers and commentary sources.

A pre-release internal check of all 88 files (the lab's own, not a third-party review) found no
event-level rows, no odds or price series, no commentary or caption text, no player tables and no provider
response bodies.

**Why track these at all?**

1. *Null and negative results stay on the record.* No verdict in this folder is an acceptance.
   Committing the ledgers makes that hard to quietly forget.
2. *Cohorts can be audited without the raw data.* Every dropped match carries a reason code.
3. *Hashes make inputs checkable.* Anyone with their own copy of a source file can compare its SHA-256
   with the one the lab recorded.
4. *Code depends on the fixed filenames.* Build scripts write here under fixed names, and three test modules
   read from here (`tests/test_evaluation_cohort_lineage.py`, `tests/test_evidence_power_consolidation.py`,
   `tests/test_context_features.py`). Please do not rename, move or hand-edit these files.

**What this folder cannot do.** You cannot recompute a metric from these files alone. They record results
and provenance; re-running an evaluation needs the raw data, which you would have to obtain yourself
(see [`../../docs/DATA_SOURCES.md`](../../docs/DATA_SOURCES.md) and
[`../../docs/TESTING_AND_DATA_DEPENDENCIES.md`](../../docs/TESTING_AND_DATA_DEPENDENCIES.md)).

**Conventions**

- Most ledgers come as a `.json` + `.csv` pair. The JSON usually carries header fields (build time,
  counts, reference model); the CSV is rows only. A few JSON files, such as `model_decision_ledger.json`,
  are a bare list with no header. Row counts below mean data rows, excluding the CSV header line.
- Many files carry the label string
  `research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible`. It means exactly
  what it says.
- Timestamps inside the files are UTC. **Every file is a point-in-time snapshot**, written once by a script and usually never
  refreshed. Some were later overtaken by events — see [section 4](#4-read-this-before-trusting-a-number).

---

## 2. Decision vocabulary

### 2.1 Model verdicts

These appear in the `verdict`, `final_status` or `classification` column of the decision ledgers.

| Term | Meaning | Where it appears |
|---|---|---|
| `reference_only` | Either the model *is* the reference baseline for its family, or it is a candidate that did not clear the acceptance rules against that reference. The reference stays in place. This is the most common verdict in the folder. | All five decision ledgers |
| `rejected` | The candidate was turned down. In the dynamic in-play ledger it means a "safety" rule failed (calibration worse than the reference beyond tolerance, club-only test rows, or an xG-integrity problem). In the residual ledger it marks goal-intensity and near-term-scoring candidates that did not improve on their reference. | `model_decision_ledger`, `residual_goal_intensity_decision_ledger` |
| `data_insufficient` | Too little data to judge, so there is **no verdict on merit**. Triggers: fewer than 30 matches or 200 test rows, fewer than 2 folds, too few positive events (the sending-off models were gated off below 150 positives), or no output produced for that model in that run. In the prospective script it is reserved for fewer than 20 fixtures. | `event_process_…`, `residual_…`, `hierarchical_transfer_eval_audit.json`, `international_event_lake_decision_package.json` (see [4h](#note-h)), and the club-only blocks of the two 58-match power files |
| `no_evidence_of_improvement` | Prospective benchmark only. For this model, no paired difference against B1 *or* against the market has a 95% confidence interval that excludes zero in its favour. Read it as "no evidence of improvement at this sample size" (34 fixtures, early-line market comparator). It does not say the models are equal. | `prospective_model_decision_ledger` |
| `market_comparator_only` | The no-vig bookmaker consensus (`M2_market`). A read-only yardstick, never a candidate. In the prospective benchmark this is an **early line, not a closing line** — see [`../../docs/ERRATA.md`](../../docs/ERRATA.md), E2. | `prospective_model_decision_ledger` |
| `exploratory_underpowered` | Defined in [`../../scripts/prospective_benchmark_v1.py`](../../scripts/prospective_benchmark_v1.py) for a model with at least one paired difference whose 95% CI excludes zero in its favour. The script's own note labels that case "not confirmatory; not promotable". **Never issued** — no tracked ledger contains it. | Defined, unused |
| `research_candidate_for_future_shadow_review` | The only "pass" verdict. It would make a model eligible for a later shadow review, never for runtime use. **Never issued** — zero rows in any tracked ledger. | Defined, unused |

Two related labels live elsewhere: `invalid_due_to_model_selection_on_test_set` is recorded in
[`../../notes/research/inplay_result_status_registry.yaml`](../../notes/research/inplay_result_status_registry.yaml),
and the sample-size tiers A–D are defined in [`../../docs/GLOSSARY.md`](../../docs/GLOSSARY.md).

### 2.2 How a verdict is reached

The in-play research lines share an acceptance gate of about eight rules. The code comments call these
"preregistered" promotion rules. Read that as *pre-specified inside this repository and self-attested*;
nothing was registered externally. A candidate must satisfy **all** of them:

1. lower pooled out-of-sample RPS than the reference (Brier score for binary targets);
2. favourable in most held-out folds;
3. a match-level paired bootstrap 95% CI for the difference lies wholly below zero;
4. draw-channel calibration (ECE) not worse than the reference by more than 0.02;
5. the advantage survives removing the single most favourable tournament;
6. every test row is an international match;
7. xG models are scored only on the exact-bridge subset with non-zero xG;
8. enough matches, rows and folds to evaluate.

**The gate exists in several near-duplicate implementations, and they differ in detail:**

| Implementation | Used for | Differences worth knowing |
|---|---|---|
| [`dynamic_eval.py`](../../src/wcdrawlab/research/dynamic_eval.py) (`evaluate_candidate_rule`) | `model_decision_ledger` | "Most folds" means at least 4 folds or at least 75%. Failing rule 4, 6 or 7 gives `rejected`; failing only rules 1, 2, 3 or 5 gives `reference_only`. |
| [`_ep_lib.py`](../../scripts/event_process_jobs/_ep_lib.py) and [`_rg.py`](../../scripts/residual_jobs/_rg.py) (`candidate_verdict`) | `event_process_…` and `residual_…` ledgers | "Most folds" means at least 60%. Rule 5 is not checked separately. A candidate that does not improve the pooled metric is `reference_only`; one that improves it but fails another rule would be `rejected` (no row took that path). The residual ledger builder relabels its goal-intensity and near-term-scoring candidates that did not improve as `rejected`. |
| [`event_process/eval.py`](../../src/wcdrawlab/research/event_process/eval.py) plus [`rerun_international_event_lake_models.py`](../../scripts/rerun_international_event_lake_models.py) | `international_event_lake_…` ledger | "Most folds" means at least 75%. The rerun script then adds **three further gates**: pooled log-loss not worse than the reference, at least 60% of eligible matches scored, and forward-chain RPS not worse than the reference. |

The line between `reference_only` and `rejected` is therefore **not uniform across ledgers**. For a reader
both mean the same thing: the model was not accepted. Always read the `reason` column.

One consequence matters when you scan these files: **a lower point RPS is not a pass.** Several rows show
a lower point RPS than their reference and were still not accepted; see [4g](#note-g).

### 2.3 Evidence-registry claim statuses

Used in `research_evidence_registry.{json,csv}`, which re-checks earlier headline counts against what was
actually on disk.

| Status | Meaning | Records |
|---|---|---|
| `verified_current` | The count was reconstructed from a file whose on-disk state matched it at build time. | 2 |
| `verified_historical` | The artifact is real and internally consistent, but describes an earlier on-disk state (or the raw data was not present where the registry ran). | 6 |
| `contradicted` | The artifact's headline count disagreed with what was on disk when the registry was built. | 1 (`statsbomb.cache_audit`) |
| `incomplete` | The artifact is present but a needed count could not be derived locally. | 1 |
| `stale`, `needs_rerun` | Defined by the builder script; not assigned to any registry record. | 0 |

### 2.4 Smaller vocabularies

- **Reproducibility classes** (`evaluation_reproducibility_audit.json`): `reproducible_verified` (1
  evaluation), `reproducible_with_limitations` (5), `needs_rerun` (1), `cannot_reproduce` (0).
- **Failure-matrix verdicts** (`prospective_score_harvest_failure_matrix.json`): `TRUE_PRIMARY`,
  `TRUE_contributory`, `TRUE_analog`, `contributory_not_causal`, `false`, `false_for_universe`,
  `not_applicable`.
- **Live-readiness classes** (`live_readiness_matrix.json`): nine are defined. Of 21 feature families, 6 are
  `potentially_live_with_verified_provider`, 6 `blocked_by_no_point_in_time_history`, 5
  `blocked_by_missing_provider_contract`, 3 `blocked_by_latency` and 1 `historical_research_ready`. **None
  is `live_eligible`.**

---

## 3. Index by family

All 88 files are listed once below. Notes are in [`../../notes/research/`](../../notes/research/README.md).

| # | Family | Files |
|---|---|---|
| 3.1 | Model decision ledgers | 10 |
| 3.2 | Cohort lineage and exclusion ledgers | 6 |
| 3.3 | Power analyses and minimum-evidence requirements | 5 |
| 3.4 | Corpus and fixture manifests | 18 |
| 3.5 | Event-lake, bridge and xG-join manifests and audits | 19 |
| 3.6 | Hierarchical-transfer artifacts | 7 |
| 3.7 | Evidence and truth registries | 5 |
| 3.8 | Prospective-evaluation artifacts | 4 (+ the ledger counted in 3.1) |
| 3.9 | Provider and commentary catalogs | 8 |
| 3.10 | Readiness matrices and feature catalog | 4 |
| 3.11 | Tournament reference data | 2 |

### 3.1 Model decision ledgers

**Question answered:** for each research line, which models were tried, how did each score against the
line's reference, and what was decided?

| Research line | Files | Models | Verdicts | Explained in |
|---|---|---|---|---|
| Dynamic in-play modelling (API-Football, 627 internationals) | `model_decision_ledger.{json,csv}` | 11 | 7 `rejected`, 4 `reference_only` (three of those are the baselines R0–R2) | [`DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md`](../../notes/research/DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md) |
| Event-process intelligence (58-match cohort) | `event_process_model_decision_ledger.{json,csv}` | 22 | 20 `reference_only`, 2 `data_insufficient` | [`EVENT_PROCESS_INTELLIGENCE_V1_COMPLETION.md`](../../notes/research/EVENT_PROCESS_INTELLIGENCE_V1_COMPLETION.md) |
| Residual goal intensity (58-match cohort) | `residual_goal_intensity_decision_ledger.{json,csv}` | 16 | 7 `reference_only`, 6 `rejected`, 3 `data_insufficient` | [`RESIDUAL_GOAL_INTENSITY_V1_COMPLETION.md`](../../notes/research/RESIDUAL_GOAL_INTENSITY_V1_COMPLETION.md) |
| Event-lake rerun (231 eligible matches) | `international_event_lake_model_decision_ledger.{json,csv}` | 10 | 10 `reference_only` | [`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md`](../../notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md) |
| Prospective 2026 benchmark (34 scored fixtures, exploratory tier; the market comparator is an early line, not a closing line — see [3.8](#38-prospective-evaluation-artifacts)) | `prospective_model_decision_ledger.{json,csv}` | 5 | 1 `reference_only`, 1 `market_comparator_only`, 3 `no_evidence_of_improvement` | [`PROSPECTIVE_MARKET_BENCHMARK_V1.md`](../../notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md), [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](../../notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md) |
| Hierarchical club→international transfer | **absent** — see [4c](#note-c) | — | — | [`HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md`](../../notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md) |

**Across all five ledgers: 64 model rows, zero accepted candidates.** The 64 rows include each line's
reference models and the market comparator, and the 58-match and 231-match event-process rows are the same
ten models (e0–e9) evaluated twice. Given the power analyses in
[3.3](#33-power-analyses-and-minimum-evidence-requirements), read these as "no evidence of improvement at
this sample size", not as proof that nothing could help.

Key fields:

- `model_decision_ledger`: `model_id`, `dataset_version`, `source_manifest_version`, `rps`, `logloss`,
  `brier_draw`, `n_folds`, `reference`, `final_status`, `reason`, `promotion`.
- `event_process_…` and `residual_…`: `model_id`, `verdict`, `reason`, `reference_oos_metric`,
  `model_oos_metric`, `labels`; the JSON adds `evidence` (one boolean per rule, plus `n_matches`,
  `n_test_rows`, `fold_win_fraction`) and a `reference_models` map. The metric is RPS for win/draw/loss
  models, Brier score for binary targets and Poisson deviance for goal-intensity models. Lower is better
  for all three.
- `international_event_lake_…`: `model_id`, `is_reference`, `loco_rps`, `loco_logloss`, `loco_brier_draw`,
  `forward_chain_rps`, `rps_delta_vs_R0`, `bootstrap_favors`, `coverage_fraction`, `verdict`, `reason`. The
  JSON adds a `verdicts` map with rule-by-rule evidence for every model (per-fold deltas, bootstrap CI,
  calibration, log-loss and forward-chain checks).
- `prospective_…`: `model`, `classification`, `tier`, `n_fixtures`, `rps`, `log_loss`, `draw_brier`, `note`,
  `runtime_ready`, `trade_eligible` (the last two are `false` on every row). The JSON adds `strata`,
  including `by_window`: 31 baseline, 2 final-pre-kickoff, 1 T-90.

**One reference model, several names.** The remaining-time Poisson reference appears as
`research.wdl.remaining_time_poisson_r2`, `research.event_process.e2`, `research.residual.w2_reference_r0`
and `research.transfer.w2_reference_t0`, depending on the line. Some `reason` strings call it
"parameter-free". Read that as *unfitted*: it has hand-set constants (base goal rate 1.35, Elo coefficient
0.20) and nothing estimated from data. See [`../../docs/GLOSSARY.md`](../../docs/GLOSSARY.md).

### 3.2 Cohort lineage and exclusion ledgers

**Question answered:** which matches reached each evaluation, and why did the others drop out?

| File | Rows | Key fields | What it shows |
|---|---|---|---|
| `evaluation_cohort_lineage.{json,csv}` | 298 | `sb_match_id`, `api_fixture_id`, `competition_label`, `kickoff_date`, `bridge_confidence`, `comp_type`, one true/false column per stage (9 stages), `dropped_at_stage`, `drop_reason`, `drop_detail` | The funnel 298 candidate internationals → 258 exact-bridged → 58 with event files on disk at the time. 46 of the 58 are forward-chain test matches; the earliest tournament is train-only. JSON `meta` records `no_silent_disappearance: true` and `unexplained_drops: []`. |
| `cohort_exclusion_ledger.{json,csv}` | 252 | `sb_match_id`, `api_fixture_id`, `competition_label`, `kickoff_date`, `dropped_at_stage`, `drop_reason`, `detail` | One row per drop: 200 `missing_statsbomb_events`, 38 `ambiguous_bridge`, 12 `held_out_fold_rule`, 2 `failed_reconciliation`. |
| `residual_58_match_cohort.csv` | 58 | `source_match_id`, `competition_label`, `kickoff_date`, `target_wdl`, `reg_home_goals`, `reg_away_goals`, `n_snapshots`, `n_events`, `in_cohort` | The exact 58 matches behind the event-process and residual results. |
| `residual_58_match_audit.json` | — | `funnel`, `recompute_forward_chain`, `recompute_loco_pooled`, `match_level`, `comparison`, `verdict` | An internal cold reconstruction of that cohort and of the reference model's (R0) metrics. Recomputed and reported values agree (forward-chain RPS 0.15263, LOCO RPS 0.14906, absolute difference 0.0). This checks reproducibility of the reference, not any candidate. |

Explained in: [`evaluation_cohort_lineage_report.md`](../../notes/research/evaluation_cohort_lineage_report.md),
[`residual_58_match_audit.md`](../../notes/research/residual_58_match_audit.md),
[`EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md`](../../notes/research/EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md).

This family describes the **58-match state**. The later restoration to 258 objects and 231 eligible matches
is in [3.5](#35-event-lake-bridge-and-xg-join-manifests-and-audits).

### 3.3 Power analyses and minimum-evidence requirements

**Question answered:** given the noise actually observed, how many independent matches would it take to
detect an improvement of a given size — and does adding more snapshots of the same matches help? (It does
not.)

| File | Cohort | Key fields | Headline |
|---|---|---|---|
| `match_level_power_analysis.json` | 58 matches | `unit_of_independence`, `variance_calibration`, `decision_rule`, `current_power_at_58_matches`, `matches_and_tournaments_needed`, `more_snapshots_same_matches`, `seeds` | Inflating snapshots 1×/2×/4×/8× on the same 58 matches left power flat (0.30 / 0.29 / 0.27 / 0.29 for a 0.003 RPS gain). |
| `minimum_evidence_requirements.json` | 58 matches | `observed_current_state`, `minimum_matches_by_effect_size`, `headline_answers`, `acceptance_protocol_recommendation` | Projects about 150 matches for a 0.005 gain at 80% power. **Superseded** — see [4i](#note-i). |
| `international_event_lake_power_analysis.{json,md}` | 231 matches | `template_info`, `current_power_at_observed_M`, `matches_needed_for_power`, `tournaments_needed_for_power`, `more_snapshots_same_matches`, `coverage_imbalance_effect`, `power_estimate_uncertainty` | Power for a 0.005 absolute RPS gain is 0.28; 80% power first appears at the 1,200-match grid point. |
| `international_event_lake_minimum_evidence_requirements.json` | 231 matches | `minimum_matches_for_80pct_power`, `minimum_tournaments_for_80pct_power`, `current_cohort_detectable_at_80pct` (empty list) | No effect size on the grid is detectable at 80% power with the current cohort. |

Explained in: [`match_level_power_analysis.md`](../../notes/research/match_level_power_analysis.md),
[`minimum_evidence_requirements.md`](../../notes/research/minimum_evidence_requirements.md),
[`EVIDENCE_POWER_DECISION_MEMO.md`](../../notes/research/EVIDENCE_POWER_DECISION_MEMO.md).

These files are why the nulls elsewhere are worded "no evidence of improvement at this sample size" and
not "no effect".

### 3.4 Corpus and fixture manifests

**Question answered:** exactly which fixtures were selected for each corpus, by what rule, and how much of
the plan was actually retrieved?

**API-Football (identifier lists — no scores, events, lineups or player data)**

| File | Rows | Key fields | Notes |
|---|---|---|---|
| `api_football_corpus_fixture_manifest.{json,csv}` | 2,383 | `canonical_match_id`, `provider_fixture_id`, `cohort`, `comp_type`, `league`, `season`, `kickoff_utc`, `status`, `eligibility`, `inclusion_rule`, `expected_endpoints`, `raw_status`, `reconciliation_status` | 627 Cohort A internationals and 1,473 Cohort B club fixtures included; 283 `excluded_truncated`. Selection used fixture metadata only. JSON header records the quota budget and `truncation_rule`. The notes record retrieval of 1,120 of the 2,100 included fixtures (the first 900, then the 220 below); the status columns here were never updated ([4a](#note-a)). |
| `api_football_red_threshold_extension_manifest.csv` | 220 | same identifier fields, `inclusion_rule` | The next 220 included club fixtures in manifest order (`extension_next_220_manifest_order`), retrieved to test whether sendings-off would reach a 150-event threshold (the recorded count went from 123 to 176). |
| `player_history_corpus_manifest.{json,csv}` | 2,000 | `canonical_match_id`, `provider_fixture_id`, `league_name`, `season`, `kickoff_utc`, `inclusion_rule`, `raw_status`, `reconciliation_status` | Fixed-seed, hash-stratified sample: 100 fixtures per league-season, five European leagues, seasons 2020–2023, all club. |
| `full_corpus_execution_manifest.{json,csv}` | 2,000 | `raw_events_state`, `raw_lineups_state`, `execution_status`; JSON header `complete_eligible_fixtures`, `outstanding`, `manifest_completion_rate`, `gate_95pct_met` | **Stale snapshot** — see [4a](#note-a). |
| `corpus_coverage_ledger.json` | — | `done`, `coverage_before`, `coverage_after` (each with `per_root_full_events_and_lineups`, `raw_backed_across_registered_roots`, `missing_ids`, `coverage_rate`), `gate_95pct_raw_backed`, `self_contained_canonical`, `note` | **The current record** of player-history corpus completion: 2,000 done, coverage 1.0. Counts files actually on disk, not the length of a "done" list. |
| `canonical_counts_ledger.json` | — | `reconciled_fixtures`, `regulation_exact`, `exact_rate`, `canonical_sendings_off_total`, `scope_note` | 960 reconciled fixtures, all regulation-exact, 128 sendings-off — a union across the data roots visible when it was built. Read `scope_note`. |

Scope caution: event-derived regulation scores matched the provider's own full-time score on the 900
audited fixtures, later 1,120 after the extension. That is an internal-consistency check against the same
provider, and it is **not** claimed for the 2,000-fixture player-history pull.

**StatsBomb Open Data (match indexes — no event rows)**

| File | Rows | Key fields | Notes |
|---|---|---|---|
| `statsbomb_competition_catalog.csv` | 80 | competition/season ids and names, `international`, per-feature availability flags, `n_matches`, `domain_shift_risk` | One row per competition-season; 17 are international. |
| `statsbomb_event_process_catalog.{json,csv}` | 2,651 | `match_id`, `competition_id`, `season_id`, `competition`, `season`, `match_date`, `home`, `away` | Match index only. |
| `event_process_auxiliary_manifest.{json,csv}` | 669 | `rank` plus the same index fields; JSON header `seed`, `target`, `cap_per_group`, `n_groups` | A seeded sample selected as auxiliary "club-domain" training data: 55 competition-season groups, at most 80 matches per group. 668 rows are club matches; one is a FIFA U20 World Cup match. |
| `official_modern_international_catalog.{json,csv}` | 333 | `sb_match_id`, competition and season fields, `home`, `away`, `home_score`, `away_score`, `fulltime_result`, `competition_stage`, `source_url` | The one family here that carries final scores, copied from the public StatsBomb match listings, each with its source URL. |
| `official_modern_international_selection_manifest.{json,csv}` | 12 | `competition`, `season`, `n_matches`, `matches_sha256`, `matches_url` | The 12 competition-seasons admitted (four competitions), with a hash of each source listing. Despite the name, six of them are pre-1991 World Cups contributing 19 matches in total. |

Explained in: [`api_football_corpus_sampling_protocol.md`](../../notes/research/api_football_corpus_sampling_protocol.md),
[`api_football_red_threshold_extension_protocol.md`](../../notes/research/api_football_red_threshold_extension_protocol.md),
[`player_history_sampling_protocol.md`](../../notes/research/player_history_sampling_protocol.md),
[`full_corpus_execution_protocol.md`](../../notes/research/full_corpus_execution_protocol.md),
[`API_FOOTBALL_HISTORICAL_CORPUS_COMPLETION.md`](../../notes/research/API_FOOTBALL_HISTORICAL_CORPUS_COMPLETION.md),
[`statsbomb_coverage_audit.md`](../../notes/research/statsbomb_coverage_audit.md),
[`official_modern_international_catalog_report.md`](../../notes/research/official_modern_international_catalog_report.md).
The coverage gate itself is [`../../src/wcdrawlab/research/corpus_coverage.py`](../../src/wcdrawlab/research/corpus_coverage.py).

### 3.5 Event-lake, bridge and xG-join manifests and audits

**Question answered:** are the StatsBomb event files for the 258 bridged internationals really present and
hash-verified, which of them are usable as evaluation targets, and what did the rerun on them find?

These files were written over three days in which the number of event files actually on disk changed: 258
reported cached, then 60 found (the evidence registry describes the earlier pull as "since pruned"), then
258 restored into a hash-verified lake. They are listed **in time order**, because the early ones describe a
state that no longer held a day later.

Times are UTC build stamps taken from inside each file. Rows that show only a date have no internal stamp
and are dated by their commit.

| When | File | Key fields | What it recorded |
|---|---|---|---|
| 2026-06-26 | `statsbomb_cache_audit.json` | `total_exact_bridge`, `valid_cached`, `xg_field_available`, `completion_rate`, `per_match` (258 entries) | 258 of 258 event files cached. Later marked `contradicted` by the evidence registry — see [4a](#note-a). |
| 2026-06-26 | `xg_snapshot_join_audit.json` | `checks`, `xg_eligible_international_snapshots`, `distinct_matches`, `rows_nonzero_xg` | 4,386 regulation-time snapshots over 258 matches; 4,323 rows with non-zero xG; eight structural checks pass. |
| 2026-06-26 | `dynamic_xg_state_audit.json`, `dynamic_xg_state_coverage.json` | `self_test.checks`, `structural_audit.checks`; `snapshots_built`, `grid_minutes`, `by_competition_rows`, `leakage_rules` | Leakage checks for the xG state features (xG at minute *t* uses only shots at or before *t*) and their coverage: 17 decision minutes per match. |
| 2026-06-28 06:01 | `international_event_lake_audit.json` | `integrity`, `lake_objects`, `present_in_lake`, `missing_from_lake`, `missing_match_ids`, `source_quality` | **Pre-restoration snapshot:** 59 objects present, 199 missing. |
| 2026-06-28 06:02 | `international_event_lake_index_summary.json` | `object_count`, `hash_verified_objects`, `integrity_all_ok` | **Pre-restoration snapshot:** 60 objects. |
| 2026-06-28 07:10 | `legacy_international_bridge_restoration_manifest.{json,csv}` (258 rows) | `bridge_id`, `sb_match_id`, `local_file_status`, `local_sha256`, `lake_status`, `lake_sha256`, `retrieval_decision`, `reason` | All 258 objects are `present` in the lake. The old local cache still held 58 of them (`local_file_status: valid`), and for those 58 the local and lake SHA-256 values are equal; the other 200 rows are `absent` locally and have no local hash to compare. |
| 2026-06-28 07:10 | `expanded_international_bridge_manifest.{json,csv}` (333 rows) | `official_sb_match_id`, `local_bridge_id`, `official_fulltime_result`, `local_regulation_result`, `orientation`, `classification` | The 333-match official catalog against the 258 local fixtures: 250 `exact`, 71 `missing_local_match`, 8 `score_mismatch`, 4 `team_name_mismatch`. |
| 2026-06-28 07:16 | `international_event_lake_cohort_manifest.{json,csv}` (258 rows, 35 columns) | `lake_sha256`, `reconciliation_status`, `target_wdl`, `reg_home_goals`, `reg_away_goals`, per-match counts, seven `target_eligible_*` flags, `exclusion_reason`, `primary_fold`, `loco_fold` | **The current cohort:** 258 hash-verified matches, 231 eligible as targets, 27 excluded, 32,359 snapshots, five tournaments, `no_2026_wc_guarantee: true`. |
| same build | `international_event_lake_cohort_exclusions.csv` (27 rows), `international_event_lake_cohort_report.md` | `sb_match_id`, `exclusion_reason` | All 27 exclusions are W/D/L target conflicts — see [4f](#note-f). The literal string in the column is `wdl_target_conflict:wdl_target_conflict`. The report is a readable summary of the manifest. |
| 2026-06-28 07:47 | `international_event_lake_evaluation_metrics.json`, `international_event_lake_bootstrap.json`, `international_event_lake_calibration.json` | per-model `loco_rps`, `loco_logloss`, `loco_brier_draw`, `forward_chain_rps`; `ablations`; per-model `mean_delta`, `ci95`, `favors_candidate`; per-model draw-channel `slope`, `intercept`, `ece` | The rerun of ten event-process models on 231 matches (28,773 evaluation rows; 1,000 match-level bootstrap resamples). Outcome: ten `reference_only` verdicts, nothing accepted. Read [4g](#note-g) before quoting any delta from these files. |
| same run | `international_event_lake_reproducibility_audit.json` | `all_inputs_lake_hash_backed`, `n_distinct_lake_source_hashes`, `bootstrap_unit`, `deterministic`, `no_2026_world_cup` | Every evaluation input traced to a lake hash; bootstrap unit is the match. |
| same run | `international_event_lake_decision_package.json` | `decision_ledger`, `reproducibility`, `source_quality`, `power` | A packaging summary. Its `decision_ledger` block is an unfilled default — see [4h](#note-h). `source_quality` records 258 objects: 58 copied from the local cache, 200 retrieved from the official StatsBomb open-data host. |

The matching per-model ledger is in [3.1](#31-model-decision-ledgers); the power analysis is in
[3.3](#33-power-analyses-and-minimum-evidence-requirements).

Explained in: [`statsbomb_full_event_cache_report.md`](../../notes/research/statsbomb_full_event_cache_report.md),
[`complete_xg_snapshot_join_report.md`](../../notes/research/complete_xg_snapshot_join_report.md),
[`international_event_lake_audit_report.md`](../../notes/research/international_event_lake_audit_report.md),
[`legacy_statsbomb_cache_restoration_protocol.md`](../../notes/research/legacy_statsbomb_cache_restoration_protocol.md),
[`expanded_international_bridge_report.md`](../../notes/research/expanded_international_bridge_report.md),
[`international_event_lake_data_contract.md`](../../notes/research/international_event_lake_data_contract.md),
[`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md`](../../notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md).

### 3.6 Hierarchical-transfer artifacts

**Question answered:** can club football data help an international in-play model? **The honest answer in
this repository is "untested".** The run ended with zero club training rows, so cross-domain lift was never
measured, and no model improved on the reference T0.

| File | Rows | Key fields | What it shows |
|---|---|---|---|
| `domain_event_process_inventory.{json,csv}` | 927 (258 international, 669 club) | 55 columns: `domain`, match identifiers, `source_sha256`, per-match counts (`n_events`, `n_shots`, `n_shots_with_xg`, `n_pressure_events`, cards, substitutions, `snapshot_count`), availability flags, fold labels; JSON adds a 60-row `per_group_rollup` | A per-match coverage inventory. Aggregate counts only — no event rows, coordinates or player names. The largest file in the folder (about 1.9 MB as JSON). |
| `domain_normalized_transfer_audit.json` | — | `row_source`, `n_rows`, `row_roles`, `n_folds`, `n_intl_test_matches`, **`n_club_train_matches`**, `checks` (11) | The real materialised dataset: 93,940 rows, 194 international test matches, four folds, all 11 invariants pass — and **`n_club_train_matches: 0`**. |
| `hierarchical_feature_stability_registry.{json,csv}` | 22 | `feature`, `class`, `reason`, `transfer_eligible`, `single_domain_gate` | 19 features classed `transfer_eligible`, 3 `always_excluded`. The header records `single_domain_train: true`. |
| `hierarchical_transfer_repair_log.json` | — | `defect`, `before_count`, `after_count`, `fix`, `regression_tests_added`, `second_defect` | The first defect (club event root not registered: 0 → 669 files) was fixed. The `second_defect` has status `diagnosed_not_yet_repaired` and is the reason club training rows stayed at zero. |
| `hierarchical_transfer_eval_audit.json` | — | `dataset`, `headline_pooled_rps`, `candidate_verdict` | **Synthetic self-test output. Never quote it** — see [4b](#note-b). |
| *(decision ledger)* | — | — | **Absent** — see [4c](#note-c). |

Explained in: [`HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md`](../../notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md),
[`hierarchical_transfer_club_root_repair.md`](../../notes/research/hierarchical_transfer_club_root_repair.md),
[`domain_event_process_inventory_report.md`](../../notes/research/domain_event_process_inventory_report.md),
[`domain_normalized_transfer_audit_report.md`](../../notes/research/domain_normalized_transfer_audit_report.md),
[`domain_shift_and_feature_stability_report.md`](../../notes/research/domain_shift_and_feature_stability_report.md).

### 3.7 Evidence and truth registries

**Question answered:** when two documents gave different counts, which was right — and can each major
evaluation still be traced back to its inputs?

| File | Rows | Key fields | What it shows |
|---|---|---|---|
| `research_truth_registry.{json,csv}` | 15 (CSV: `claim`, `key`, `value`) | `locations` (per data root: fixtures listed, with events, reconciled, sendings-off), `resolved_claims` | A rescan of raw files (committed 2026-06-26; the file carries no build time) that resolved four conflicting claims (900 vs 1,120 fixtures; 123 vs 176 sendings-off; player-history completion; StatsBomb bridge). It found that only 60 of the 2,000 planned player-history fixtures had been retrieved, so the earlier player-impact sprint had run on a 60-fixture substitute. **Itself now a stale snapshot** — see [4a](#note-a). |
| `research_evidence_registry.{json,csv}` | 10 | `id`, `program`, `source_tag`, `commit`, `data_root`, `manifest`, `counts`, `result`, `claim_status`, `dependencies`, `next_action`, `note` | Ten headline artifacts re-checked against disk on 2026-06-28: 6 `verified_historical`, 2 `verified_current`, 1 `contradicted`, 1 `incomplete`. |
| `evaluation_reproducibility_audit.json` | 7 evaluations | `classification`, `reference_model`, `cohort`, `split_protocols`, `headline_metric_reported`, `headline_metric_recomputed`, `dimensions_present`, `bootstrap_unit_used_in_run`, `limitations`, `evidence_paths` | Each evaluation graded on six traceability dimensions: 1 `reproducible_verified`, 5 `reproducible_with_limitations`, 1 `needs_rerun`, 0 `cannot_reproduce`. |

These are internal audits carried out by the lab on its own work, not third-party reviews.

Explained in: [`research_truth_registry_report.md`](../../notes/research/research_truth_registry_report.md),
[`research_evidence_registry_report.md`](../../notes/research/research_evidence_registry_report.md),
[`evaluation_reproducibility_audit.md`](../../notes/research/evaluation_reproducibility_audit.md),
[`research_claim_verification_ledger.md`](../../notes/research/research_claim_verification_ledger.md).

### 3.8 Prospective-evaluation artifacts

**Question answered:** were the 2026 predictions really frozen before kickoff, why did the first scoring
path score nothing, and what did the benchmark decide?

| File | Rows | Key fields | What it shows |
|---|---|---|---|
| `prospective_frozen_input_manifest.json` | — | `input_hashes` (SHA-256 of the prediction ledger, forecast targets, queue, results file and the raw odds snapshot directory), `counts`, `invalid_classification` | The forensic freeze taken before scoring: 680 prediction rows, 35 fixtures, five models, 680 rows timestamped before kickoff and 0 after, 0 invalid. The timestamps are the ones the collector wrote into its own ledger; nothing outside this repository attests to them. 384 rows are the approved model `M1_B1`; 296 are shadow rows (74 each for `M2_market` and the three fixed blends). |
| `prospective_frozen_input_manifest.csv` | 680 | `match_id`, `model_version`, `prediction_timestamp`, `source_snapshot_timestamp`, `kickoff_utc`, `approval_status`, `row_index`, `valid`, `reasons` | One row per frozen prediction. Identifiers, timestamps and validity flags only — **no probabilities and no odds**. |
| `prospective_score_harvest_failure_matrix.json` | 14 candidates | `primary_root_cause`, `evidence_summary`; per candidate `hypothesis`, `verdict`, `evidence`, `scope`, `severity`, `remediation`, `regression_test` | Root-cause analysis of the silent scorer failure (0 of 680 predictions resolved a finished outcome). Primary cause: the results file was never refreshed inside the scoring step. Eight hypotheses were ruled out. |
| `prospective_model_decision_ledger.{json,csv}` | 5 | see [3.1](#31-model-decision-ledgers) | 34 scored fixtures, exploratory tier, nothing promoted. |
| `future_2026_prospective_queue.csv` | 72 | `match_id`, `home`, `away`, `kickoff_utc`, `stage`, `status`, `state`, `reason`, `anchor_p_home/draw/away`, `scheduled_windows`, `frozen_model_version`, `scoring_status` | The queue for the frozen **in-play** model (`m2_frozen@v2`: the in-play M2, an unfitted remaining-time Poisson — not the pre-match `M2_market`) over the 72 group fixtures: 28 `eligible`, 44 `skipped` (43 because the match had already finished when the queue was built, one because it was in progress). The `anchor_p_*` columns are the lab's own Elo-based probabilities, not odds. **`scoring_status` is `pending` on all 72 rows** — no frozen in-play model was ever scored prospectively. |

Two caveats travel with every number in this family:

- The market comparator is an **early line, not a closing line**. For 31 of the 34 scored fixtures the
  primary snapshot is a 2026-06-21 baseline snapshot, a median of roughly 98 hours before kickoff, because
  47 later snapshots were silently ignored ([`../../docs/ERRATA.md`](../../docs/ERRATA.md), E2). Row 10 of
  the failure matrix marks "snapshot-type parsing excludes valid rows" as `false`. That verdict is about
  snapshot selection in the scoring step. The audit did not detect the separate ingestion defect described
  in E2, so do not read row 10 as a clean bill of health for the snapshot pipeline.
- The snapshot-selection rule was pre-specified and outcome-independent, but that ordering is self-attested
  inside this repository: [`prospective_score_harvest_preregistration.md`](../../notes/research/prospective_score_harvest_preregistration.md).

Explained in: [`prospective_frozen_input_audit.md`](../../notes/research/prospective_frozen_input_audit.md),
[`prospective_score_harvest_root_cause_audit.md`](../../notes/research/prospective_score_harvest_root_cause_audit.md),
[`PROSPECTIVE_SCORE_HARVEST_AND_BENCHMARK_V1_COMPLETION.md`](../../notes/research/PROSPECTIVE_SCORE_HARVEST_AND_BENCHMARK_V1_COMPLETION.md),
[`future_2026_prospective_queue_audit.md`](../../notes/research/future_2026_prospective_queue_audit.md).
Column definitions: [`../../docs/PROSPECTIVE_DATA_DICTIONARY.md`](../../docs/PROSPECTIVE_DATA_DICTIONARY.md) and
[`../../docs/SCORE_HARVEST_GUIDE.md`](../../docs/SCORE_HARVEST_GUIDE.md).

### 3.9 Provider and commentary catalogs

**Question answered:** what could each data source supply, under what rights, and what did a small real
sample of the paid API actually contain?

| File | Rows | Key fields | What it shows |
|---|---|---|---|
| `structured_event_provider_catalog.{json,csv}` | 5 vendors | JSON: `provider`, `verified`, `evidence_urls`, `fields`, `rights`, `procurement`, `uncertainties`; CSV flattens these into 29 columns | Desk research on five event-data vendors. |
| `api_football_empirical_coverage.{json,csv}` | 11 competitions | `label`, `league`, `season`, `n_fixtures`, `event_types`, true/false flags such as `has_owngoal`, `has_var`, `lineup_ok`, `has_player_id`, `has_shots`, `has_xg`; JSON header `requests_made` | A **sampled** audit of the paid API-Football plan: 27 read-only requests, one representative fixture per deep sample. Coverage flags and counts only. |
| `commentary_source_catalog.{json,csv}` | 8 sources | `source_id`, `owner`, `access`, `license`, `languages`, `event_vs_pub_time`, `live_latency`, `modeling_rights`, `commercial_rights`, `redistribution`, `legal_status`, `recommendation` | Rights and timing research on commentary sources. **Contains no commentary text.** |
| `soccernet_action_label_catalog.{json,csv}` | 2 sources | `source`, `access`, `classes`, `event_time`, `pub_time`, `nda`, `license`, `classification` | Access and licence status of SoccerNet label sets. The label files themselves are not tracked. |

**Disclaimer for the vendor catalogs.** They were compiled from public vendor pages in June 2026. No vendor
was contacted and nothing was purchased for this research. Many entries are marked
`unknown_requires_vendor_confirmation`. Prices and terms may be out of date. The lab is not affiliated with
or endorsed by any vendor listed. Verify with the vendor before relying on any of it.

Explained in: [`structured_event_provider_decision_matrix.md`](../../notes/research/structured_event_provider_decision_matrix.md),
[`structured_event_provider_due_diligence.md`](../../notes/research/structured_event_provider_due_diligence.md),
[`api_football_empirical_coverage_audit.md`](../../notes/research/api_football_empirical_coverage_audit.md),
[`commentary_source_landscape.md`](../../notes/research/commentary_source_landscape.md),
[`commentary_source_rights_audit.md`](../../notes/research/commentary_source_rights_audit.md),
[`soccernet_action_label_source_audit.md`](../../notes/research/soccernet_action_label_source_audit.md).

### 3.10 Readiness matrices and feature catalog

**Question answered:** which in-play feature families could ever be computed live, and where should effort
go next?

| File | Rows | Key fields | What it shows |
|---|---|---|---|
| `live_readiness_matrix.{json,csv}` | 21 feature families | `feature_family`, `primary_source`, `source_timestamp_semantics`, `classification`, `point_in_time_replay_possible`, `required_provider_fields`, `required_cadence`, `required_max_latency`, `evidence_needed_before_live` | No family is classed `live_eligible`. The central fact, stated in the header: every local artifact is post-hoc and keyed by match-clock minute; no source carries a wall-clock publication timestamp, so "replayable offline" does not imply "usable live". |
| `next_investment_decision_matrix.json` | 7 options (A–G) | `title`, `expected_information_gain`, `effort`, `gain_per_effort_rank`, `what_it_unblocks`, `go_no_go`, `falsifier`, `depends_on` | A ranked list of next steps. The top recommendation is to add more independent matches, not more features; both data-purchase options are `NO_GO_FOR_NOW`. It makes no purchase recommendation. |
| `residual_goal_intensity/feature_catalog.csv` | 54 feature columns | `column`, `family`, `source_coverage`, `gate_keeps`, `everywhere_unavailable` | The feature list for the residual line, in six families. The readiness matrix links back to it. |

Explained in: [`live_readiness_and_source_gap_analysis.md`](../../notes/research/live_readiness_and_source_gap_analysis.md),
[`NEXT_INVESTMENT_DECISION_MEMO.md`](../../notes/research/NEXT_INVESTMENT_DECISION_MEMO.md),
[`residual_feature_catalog.md`](../../notes/research/residual_feature_catalog.md).

### 3.11 Tournament reference data

| File | Rows | What it is |
|---|---|---|
| `tiebreak_rules_2026.yaml` | — | The 2026 format (48 teams, 12 groups, best eight third-placed teams advance) and the Article 13 tiebreak order, head-to-head before overall goal difference. It records its own source URLs. The rule order was taken from FIFA.com and press coverage, not from an archived regulations PDF. Implemented in [`../../src/wcdrawlab/simulation/official_standings.py`](../../src/wcdrawlab/simulation/official_standings.py). |
| `venues_2026.csv` | 16 | `venue`, `city`, `country`, `lat`, `lon`, `altitude_m` for the 16 host stadiums. Hand-compiled approximate values; the file records no source. Read by `tests/test_context_features.py`. |

The tiebreak file is explained in [`tier_1_remediation.md`](../../notes/research/tier_1_remediation.md) and
[`tier_1_data_card.md`](../../notes/research/tier_1_data_card.md). No research note documents the venue
table; its use is described in
[`../../docs/CONTEXT_FEATURE_AVAILABILITY_POLICY.md`](../../docs/CONTEXT_FEATURE_AVAILABILITY_POLICY.md).

---

## 4. Read this before trusting a number

<a id="note-a"></a>

### (a) Several manifests are stale snapshots; `corpus_coverage_ledger.json` is the current one

Files here are written once and rarely refreshed. Some describe a state that changed hours or days later,
so **tracked files contradict each other**. When they do, the later file wins.

The clearest example is the 2,000-fixture player-history corpus:

| File | Committed | What it says |
|---|---|---|
| `full_corpus_execution_manifest.json` | 2026-06-26 (`df516fa`) | `complete_eligible_fixtures: 60`, `outstanding: 1940`, `manifest_completion_rate: 0.03`, `gate_95pct_met: false`; 1,940 rows `pending` |
| `corpus_coverage_ledger.json` | 2026-06-26, about two hours later (`5ef2c31`) | `done: 2000`, `coverage_rate: 1.0`, `gate_95pct_raw_backed: true` |

**`corpus_coverage_ledger.json` is the current record.** It also documents a self-correction: its
`coverage_before` block shows that when the backfill first reported 2,000 of 2,000, only 1,940 fixtures were
raw-backed in the canonical root and 60 sat in an older root. The gate was changed to count files actually
on disk, and the 60 were copied across locally with no new API calls.

Other snapshots overtaken in the same way:

| Quantity | Stale file(s) | What they say | Current file |
|---|---|---|---|
| Player-history completion | `research_truth_registry.json` → `player_history_corpus` | planned 2,000, completed 60, rate 0.03 | `corpus_coverage_ledger.json` |
| Retrieval status per fixture | `raw_status` and `reconciliation_status` in `api_football_corpus_fixture_manifest` and `player_history_corpus_manifest` | `pending` on every row | These manifests were written when fixtures were *selected*; the status columns were never updated. Use them as selection records only. |
| StatsBomb event files on disk | `statsbomb_cache_audit.json` (2026-06-26) | 258 of 258 cached. Marked `contradicted` by `research_evidence_registry` on 2026-06-28, when it counted 60 event files on disk | `international_event_lake_cohort_manifest.json`: 258 hash-verified objects after restoration |
| Same | `research_truth_registry.json` → `statsbomb_bridge`; `international_event_lake_audit.json`; `international_event_lake_index_summary.json` | 60 cached and 0 joined; 59 present and 199 missing; 60 objects. All are earlier point-in-time states | Same as above |
| Evaluation cohort size | `evaluation_cohort_lineage`, `cohort_exclusion_ledger`, `residual_58_match_*` | 58 matches | Correct for the event-process and residual results, which ran on 58. The later rerun used 231. |

`research_truth_registry.json` is also internally inconsistent as committed. It lists the extension data
root with 0 fixtures and counts 123 sendings-off "with extension", yet it reports a 1,180-fixture union
and explains 176 as the post-extension sendings-off count. Raw data sat in several local working copies
when it was scanned, and the per-root counts do not add up to the union. Treat the 1,180 and 176 figures as
scope-dependent. `canonical_counts_ledger.json` gives a third pair (960 fixtures, 128 sendings-off) for yet
another scope.

"Current" means *the latest record in this repository*. A visitor cannot re-verify these counts, because
the raw files are not distributed. If you cite a count from this folder, name the file it came from.

<a id="note-b"></a>

### (b) `hierarchical_transfer_eval_audit.json` is synthetic

Its `dataset` field is `"synthetic_self_test"`. The pooled RPS values inside it (T0–T7) come from a synthetic
pipeline self-test on two LOCO folds. **They are not results and must never be quoted.** Its
`candidate_verdict` is `data_insufficient`.

<a id="note-c"></a>

### (c) The hierarchical-transfer decision ledger is absent

A runbook and the completion report cite `hierarchical_transfer_decision_ledger.{json,csv}`. **That file does
not exist in the current tree.** It was deleted as stale during an unfinished repair (commit `29db653`),
never regenerated, and has not been reconstructed after the fact. The deleted version is still visible in
git history (added in `37ea974`): four fold rows, each with zero club training rows and the selective gate
failing on `insufficient_club_rows`. It is not a result either.

The outcome of that line is: no model improved on the reference T0, and cross-domain transfer lift is
**untested** (zero club training rows). See [`../../docs/ERRATA.md`](../../docs/ERRATA.md), E5.

<a id="note-d"></a>

### (d) Path columns contain the original build machine's absolute paths

Fifteen files here embed paths such as `C:\Users\<name>\worldcup_data_lake\...` or names of sibling working
copies. Most occurrences are in `legacy_international_bridge_restoration_manifest.{json,csv}`
(`old_cache_root`, on the 58 rows that had a local copy), then `residual_58_match_audit.json` (`sources`)
and `prospective_frozen_input_manifest.json` (`input_hashes`). Eleven other files carry one path each, for
example `lake_root` in `international_event_lake_cohort_manifest.json`. That file's per-row
`lake_local_path` is relative to the lake root and is not machine-specific.

They are verbatim run records from the author's workstation, kept as historical provenance. The paths will
not exist on your machine, and some point to working copies that are not part of this repository. The
SHA-256 hashes recorded alongside them do not depend on the path. See
[`../../docs/ERRATA.md`](../../docs/ERRATA.md), E7.

One hash can be checked without any external data, with a catch. `prospective_frozen_input_manifest.json`
records the SHA-256 of `future_2026_prospective_queue.csv`, which is tracked here. The recorded value
matches a checkout with Windows (CRLF) line endings; the same file checked out with LF endings hashes
differently.

<a id="note-e"></a>

### (e) Third-party attribution

Several families are derived from third-party sources. They are published here as identifier lists,
match-listing fields (competition, date, team names and, in `official_modern_international_catalog`, final
scores), hashes and per-match aggregate counts. No event rows are included. By source:

- StatsBomb Open Data: `statsbomb_*`, `official_modern_international_*`, `event_process_auxiliary_manifest`,
  `domain_event_process_inventory`, the bridge manifests and the `international_event_lake_*` family.
- API-Football: fixture identifiers in the `api_football_*`, `player_history_*` and `full_corpus_*`
  manifests and in the cohort lineage files, plus the 2026 group-stage fixture list in
  `future_2026_prospective_queue.csv`.
- SoccerNet: referenced by the two commentary catalogs.

Required credits, licence terms and what is *not* redistributed are set out in
[`../../docs/DATA_SOURCES.md`](../../docs/DATA_SOURCES.md). That page also records an open item: whether the
StatsBomb match indexes should be trimmed to identifiers only is left to the maintainer, and the lab's
low-risk reading of the user agreement is not a legal judgement. The repository's MIT licence covers the
code, not third-party data.

<a id="note-f"></a>

### (f) Regulation goals here are not official final scores

`reg_home_goals` and `reg_away_goals` (cohort manifest, `residual_58_match_cohort.csv`) are **clock-gated**:
the event engine counts goals with a match-clock minute of 90 or less, which drops second-half
stoppage-time goals. For example, `sb_match_id` 7525 (Russia v Saudi Arabia, 2018) is recorded 3–0; the
official score was 5–0.

The cohort builder reconciles every match against an API-side regulation result. Of 258 matches, 207 are
`exact`, 24 are `mismatch_regulation_goals` (goal count differs, win/draw/loss outcome agrees — kept) and 27
are `wdl_target_conflict` (the outcome itself differs — excluded from every target). Those 27 are the rows
in `international_event_lake_cohort_exclusions.csv`. A flagged row is the check working, not a data error.

<a id="note-g"></a>

### (g) A lower RPS in a ledger row is not a positive result

Several rows show a lower point RPS than their reference. None was accepted, and none should be quoted as
a finding:

- **Event-lake ledger (231 matches).** Five of the nine non-reference models (e4, e6, e7, e8, e9) have a
  lower pooled LOCO RPS than the reference e2 (0.14034). For four of them the match-level bootstrap 95% CI
  includes zero. All nine have worse log-loss than e2.
- **`research.event_process.e9`** is the one most likely to be misread. Its LOCO RPS is lower than the
  reference (0.13358 vs 0.14034), it is favourable in 4 of 5 folds, and
  `international_event_lake_bootstrap.json` shows `favors_candidate: true` with a CI of [−0.0118, −0.0012].
  So it cleared the base rules. It then failed two of the rerun's further gates: its log-loss is **worse**
  (0.8226 vs 0.7463) and its forward-chain RPS is not better than the reference (0.13961 vs 0.13952). Its
  verdict is `reference_only`. One interval out of nine comparisons, with no multiplicity correction and a
  worse log-loss, is not a positive result.
- **Dynamic in-play ledger (627 internationals).** The five player-state models (p1–p5) have RPS between
  0.1489 and 0.1517 against the reference's 0.1523. All five are `rejected` on a safety rule.
- **`research.wdl.xg_player_state_x2`** in the same ledger shows RPS 0.1327 beside the reference's 0.1523,
  but `n_folds` is 2 for the xG models and 4 for the reference. The xG models were scored on the smaller
  258-match xG-bearing subset, a different population, so the two numbers are not like-for-like. Verdict:
  `reference_only`.

<a id="note-h"></a>

### (h) Two vocabularies describe one event-lake outcome

`international_event_lake_decision_package.json` says `verdict: "data_insufficient"` with
`reference_model: null`. That block is an unfilled packaging default. The per-model ledger for the same run
names the reference (`research.event_process.e2`) and records ten `reference_only` verdicts. Both describe
one outcome: no candidate cleared the gate. See [`../../docs/ERRATA.md`](../../docs/ERRATA.md), E6.

<a id="note-i"></a>

### (i) The 58-match power projection is superseded

`minimum_evidence_requirements.json` projects about 150 matches for a 0.005 RPS gain at 80% power. That
used the noise observed on 58 matches (paired-difference SD 0.0199). The template was optimistic:
`match_level_power_analysis.json` records that its template candidate scored identically to the reference
on 46 of the 58 matches (`n_matches_r4_identical_to_r0`), which shrinks the SD. The 231-match analysis used a different template pair, observed a much larger SD
(0.0593) and finds power of only 0.28 for the same gain, with 80% first reached at the 1,200-match grid
point. **Use the `international_event_lake_power_analysis` figures.** The finding that survives both
analyses is that the match, not the snapshot, is the independent unit.

<a id="note-j"></a>

### (j) One registry row mislabels a file

In `research_evidence_registry`, the record `baseline.model_decision_ledger` describes
`model_decision_ledger.json` as "pre-match baseline B0-B7 gate decisions". The file as committed holds the 11
**in-play** models of the dynamic modelling phase. The pre-match baseline gate is written up in
[`tier_2_baseline_gate.md`](../../notes/research/tier_2_baseline_gate.md) and has no ledger in this folder.

---

## 5. Loading a ledger

Nothing here needs the `wcdrawlab` package installed; the example uses only `json` and `pandas`. From the
repository root:

```python
import json
import pandas as pd

# one row per model, with its verdict
led = pd.read_csv("data/reference/international_event_lake_model_decision_ledger.csv")
print(led[["model_id", "loco_rps", "loco_logloss", "forward_chain_rps", "verdict"]])

# count verdicts across every decision ledger
for name, col in [
    ("model_decision_ledger", "final_status"),
    ("event_process_model_decision_ledger", "verdict"),
    ("residual_goal_intensity_decision_ledger", "verdict"),
    ("international_event_lake_model_decision_ledger", "verdict"),
    ("prospective_model_decision_ledger", "classification"),
]:
    print(name, pd.read_csv(f"data/reference/{name}.csv")[col].value_counts().to_dict())

# the current corpus-coverage record
print(json.load(open("data/reference/corpus_coverage_ledger.json"))["coverage_after"])
```

For definitions of RPS, LOCO, forward-chain, B1, M1–M5 and the in-play model names, see
[`../../docs/GLOSSARY.md`](../../docs/GLOSSARY.md). For known defects, see
[`../../docs/ERRATA.md`](../../docs/ERRATA.md).
