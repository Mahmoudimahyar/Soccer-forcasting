# Research notes index

This directory is the lab's complete research record: 325 notes, registries and manifests written between 2026-06-20 and 2026-06-29.

For the public release the notes were left exactly as they stood at the end of the research period. That includes claims that were later superseded, negative results, and the AI agent's own operating-state files. The git history shows no note ever deleted from this directory; later notes correct earlier ones. The only change to existing notes, made on 2026-09-20, was a dated banner (`SUPERSEDED / CORRECTED` or `CAVEAT ADDED`) placed above the original text of 26 of them. This index was added the same day.

Read the ten documents in [Start here](#start-here) first, then use the per-line sections. Before quoting a number from an older note, check [Superseded or corrected claims](#superseded-or-corrected-claims) and the repo-level [errata](../../docs/ERRATA.md).

> [!IMPORTANT]
> Everything here is research-only and paper-only. No order was ever placed, no result is a P&L figure, and nothing here is betting or financial advice.
> The "audits" and "reviews" in these notes are internal. They were run inside the same human-directed, AI-agent setup that did the work. There was no third-party review.

## Contents

1. [How to read this directory](#how-to-read-this-directory)
2. [Start here](#start-here)
3. [Research lines](#research-lines)
4. [Superseded or corrected claims](#superseded-or-corrected-claims)
5. [Operating-state files](#operating-state-files)

## How to read this directory

- **Notes are point-in-time snapshots.** When two notes disagree, the later one usually wins. The known cases are listed in [section 4](#superseded-or-corrected-claims).
- **Banners mark the known problems.** 26 notes open with a dated `SUPERSEDED / CORRECTED` or `CAVEAT ADDED` block. The original text below each banner is unchanged. In this index, † after a file name means the note carries a banner.
- **Model names collide.** There are two different models called "M2": `M2_market`, the no-vig bookmaker consensus in the pre-match shadow study, and in-play M2, a remaining-time Poisson model. The [glossary](../../docs/GLOSSARY.md#read-this-first-three-naming-traps) disambiguates them.
- **One reference model, several labels.** The unfitted remaining-time Poisson reference appears as in-play M2, `m2_frozen`, W2, R2, e2, R0 and T0, depending on the research line. The later labels are re-implementations without the Elo term ([glossary](../../docs/GLOSSARY.md#one-reference-model-seven-labels)). **Do not compare RPS values across research lines**: the datasets, snapshot grids and variants differ.
- **Filename conventions.** Files with `COMPLETION` (or `completion`) in the name are end-of-sprint reports (21 of them). Most other lowercase files are individual analyses, audits, data cards and protocols. `*_STATE.yaml`, `*_BACKLOG.md` and similar are agent control-loop state, not findings ([section 5](#operating-state-files)).
- **"Audit" and "review" mean internal.** The lab was human-directed, with an AI coding agent (Claude Code) doing the work under a written contract ([`program.md`](../../program.md)). Every audit cited in these notes was run inside that same setup. There was no third-party review.
- **"Preregistration" means in-repo and self-attested.** Protocol notes were committed to git before the results, sometimes only minutes before and, for the prospective benchmark, in the same commit. No external registry was used. This index says "pre-specified" for that reason.
- **Numbers cannot be re-derived from a fresh clone.** Raw data and `outputs/` are gitignored. See [`docs/DATA_SOURCES.md`](../../docs/DATA_SOURCES.md) and [`docs/TESTING_AND_DATA_DEPENDENCIES.md`](../../docs/TESTING_AND_DATA_DEPENDENCIES.md).
- **Local paths are provenance, not instructions.** Many notes quote the author's absolute Windows paths and sibling git worktrees that are not part of this repository (errata E7).
- **Ignore test counts quoted in notes.** Figures such as 45, 61, 151, 324 or 601 passed were true on the day. The count verified on 2026-09-20 under fresh-clone conditions is 817 passed, 51 skipped, 0 failed; [`docs/TESTING_AND_DATA_DEPENDENCIES.md`](../../docs/TESTING_AND_DATA_DEPENDENCIES.md) explains the skips.

### Verdict tags used below

The first three and the last three tags are this index's own shorthand. The middle five are the lab's decision-ledger vocabulary, defined in full in the [glossary](../../docs/GLOSSARY.md).

| Tag | Meaning in this index |
|---|---|
| `positive-modest` | An improvement whose 95% confidence interval excludes zero, on a small sample, with the caveat stated next to it. It is never a claim of a confirmed effect |
| `null` | No evidence of improvement at this sample size. This is not the same as "no effect" |
| `negative` | The candidate was measurably worse, or failed a gate fixed before testing |
| `reference_only` | Ledger status: the model is a reference, or a candidate that did not improve on the reference under the locked rules. The reference is kept |
| `rejected` | Ledger status: the candidate failed the pre-specified rules |
| `no_evidence_of_improvement` | Prospective-ledger status for the three fixed blends: no paired delta excludes zero at this sample size |
| `market_comparator_only` | Prospective-ledger status for `M2_market`: a read-only benchmark, never a candidate |
| `data_insufficient` | Too few matches or events, or the data was absent, so no evaluation was possible |
| `untested` | The run did not actually exercise the hypothesis |
| `superseded` | Replaced or corrected by a later note |
| `incomplete` | The run ended with hard gates false or artifacts missing |

## Start here

Ten documents to read first. All are in this directory.

| # | Document | Why read it |
|---|---|---|
| 1 | [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](PROSPECTIVE_SHADOW_SCORECARD_V1.md)† | The headline result, a correctly reported null. 34 World Cup 2026 group fixtures with predictions frozen before kickoff. Per-model RPS, log-loss and draw-Brier with bootstrap CIs, plus all 24 paired deltas. None excludes zero. The market comparator is an early line, not a closing line (row 2). |
| 2 | [`PROSPECTIVE_MARKET_BENCHMARK_V1.md`](PROSPECTIVE_MARKET_BENCHMARK_V1.md)† | The one-paragraph conclusion: no evidence that B1 or any blend improves on the bookmaker consensus, or the reverse. Read with the caveat that the market comparator is an **early line**, not a closing line: for 31 of 34 fixtures the odds snapshot dates from 2026-06-21, a median of about 98 hours before kickoff (errata E2). The null says nothing about B1 against a closing line. |
| 3 | [`prospective_score_harvest_preregistration.md`](prospective_score_harvest_preregistration.md) | The pre-specified, outcome-independent rule: one snapshot per fixture, the fixture as the unit of analysis, match-level bootstrap. Written after the matches were played but, by the file's own statement, before any model-vs-outcome metric was computed. That ordering is self-attested: the rule, script and results share one commit. |
| 4 | [`inplay_evaluation_reconciliation.md`](inplay_evaluation_reconciliation.md) | The internal audit that caught selection-on-test. Parameters were always fit on training data only, but the "best" in-play model was chosen after repeatedly looking at 2026 results. Each affected claim is relabelled in [`inplay_result_status_registry.yaml`](inplay_result_status_registry.yaml). |
| 5 | [`inplay_nested_evaluation.md`](inplay_nested_evaluation.md) | The clean rerun: nested leave-one-competition-out on 302 internationals with no 2026 data. The tuned models were never selected. The gain over the time+score baseline was not significant (dRPS −0.0042, 95% CI [−0.0083, +0.0002]). |
| 6 | [`tier_2_baseline_gate.md`](tier_2_baseline_gate.md) | The pre-match result. Paired bootstrap on 144 pooled development matches: no baseline robustly improves on plain Elo (B7 vs B1 dRPS +0.0011, CI [−0.0059, +0.0077]). Also discloses that an earlier blend-weight sweep had touched the 2022 gate. |
| 7 | [`match_level_power_analysis.md`](match_level_power_analysis.md)† | Why most in-play nulls should be read as "underpowered", not "no effect". The match, not the snapshot, is the independent unit: inflating snapshots 1×/2×/4×/8× on the same 58 matches left power flat. Its "Why 58" section and its 150-match projection are superseded; read it with [`international_event_lake_power_analysis.md`](../../data/reference/international_event_lake_power_analysis.md). |
| 8 | [`prospective_score_harvest_root_cause_audit.md`](prospective_score_harvest_root_cause_audit.md)† | A silent failure traced from artifacts. The collector's score step returned exit code 0 every 5 minutes and scored nothing (0 of 680 predictions resolved a finished outcome). Note that this audit marked "snapshot parsing" as a false cause and so missed a second defect, found only during the public-release review (errata E2). |
| 9 | [`commentary_silver_label_release_gate.md`](commentary_silver_label_release_gate.md) | A gate fixed before fitting and held after a near miss. 0 of 12 commentary event classes reached a Wilson 95% lower bound of 0.80 on precision, so the silver-label dataset was released empty. European club football, not the World Cup. |
| 10 | [`residual_58_match_audit.md`](residual_58_match_audit.md) | The 258 → 58 cohort funnel with every drop reasoned, the stale cache audit that overstated coverage, and an internal from-scratch recompute of the unfitted reference model that matched the reported RPS. |

## Research lines

| Line | Verdict | Sample | Git tag(s) |
|---|---|---|---|
| [Foundations and pre-match](#foundations-and-pre-match) | `null` | 144 pooled dev matches | `tier-1-complete`, `tier-1-baseline-recorded`, `approved-b1-runtime` |
| [Market comparison](#market-comparison) | `positive-modest` for one fixed blend in one retrospective tournament (the note's own word is "suggestive"; no multiplicity correction; not seen again in 2026); early claims `superseded` | 48 matches | `shadow-session-20260621-closed`, `paid-source-activation-v1`, `tier-1-complete` |
| [Prospective 2026 shadow evaluation](#prospective-2026-shadow-evaluation) | `null`, against an early-line market comparator | 34 fixtures | `prospective-score-harvest-benchmark-v1` and three earlier tags |
| [In-play models](#in-play-models) | `positive-modest` for in-play vs static (30 matches, exploratory); `null` for anything richer than the simple Poisson | 30 to 627 matches | five tags, see section |
| [Player and xG plane](#player-and-xg-plane) | `negative` / `null`; first sprint `incomplete` | 166 to 627 matches | `player-impact-xg-fusion-v1`, `research-truth-full-corpus-xg-fusion-incomplete` and two shared with In-play |
| [API-Football corpus and providers](#api-football-corpus-and-providers) | data engineering; per-shot xG `data_insufficient` at provider level | 900, then 1,120 fixtures | `api-football-historical-corpus-v1` and three others |
| [Event-process intelligence](#event-process-intelligence) | `reference_only` ×20, `data_insufficient` ×2 | 58 matches | `event-process-intelligence-v1` |
| [Residual goal intensity](#residual-goal-intensity) | `reference_only` ×7, `rejected` ×6, `data_insufficient` ×3 | 58 matches | `residual-goal-intensity-v1` |
| [Evidence, power and cohort lineage](#evidence-power-and-cohort-lineage) | methodological; explains the nulls | 58, then 231 matches | `evidence-power-consolidation-v1` |
| [International event lake](#international-event-lake) | `reference_only` ×10 | 231 matches | `international-event-lake-restoration-v1` |
| [Hierarchical transfer](#hierarchical-transfer) | `incomplete` / `untested` | 194 test matches, 0 club training rows | none |
| [Commentary NLP](#commentary-nlp) | `negative` | 254 club games | four tags, see section |

Ledger links below point to [`data/reference/`](../../data/reference/), which has its own [README](../../data/reference/README.md).

### Foundations and pre-match

**Question.** Using free data, does any pre-match model improve on plain ternary Elo (B1) for World Cup group-stage win/draw/loss forecasts?

**Verdict.** `null`. Paired bootstrap on 144 pooled development matches (folds 2010/2014/2018, 2,000 resamples): the calibrated ensemble B7 vs B1 gave dRPS +0.0011, 95% CI [−0.0059, +0.0077]. Only the frequency prior (B0) and the FIFA-ranking model (B2) differed significantly, and both were worse. B1 was approved as the sole runtime model on that basis.

**Scope.** This is a statement about the pooled development folds. On the single-read 2022 gate B1 ranked 5th of 9 by composite, so it is not uniformly best.

| File | What it holds |
|---|---|
| [`tier_2_baseline_gate.md`](tier_2_baseline_gate.md) | B0–B7 table with paired-bootstrap CIs, the 2022 gate and locked 2026 matchday-1 reads, and the conclusion that data, not architecture, is the bottleneck |
| [`model_state_reconciliation.md`](model_state_reconciliation.md)† | Internal audit that classifies every earlier claim as reproduced, historical, auxiliary or invalid. Declares the first evaluator score (composite 0.4253, computed on a corrupted table) invalid. Its V8 prequential row is an artifact (errata E1) |
| [`tier_2_existing_work_audit.md`](tier_2_existing_work_audit.md) | Caught that the V8 candidate's architecture and 0.85 blend weight had been chosen with sweeps that touched the 2022 gate. Selection was redone on dev folds only |
| [`OVERNIGHT_FINAL_REPORT.md`](OVERNIGHT_FINAL_REPORT.md)† | One 20-experiment autoresearch cycle (details in [`20260621_cycle_1.md`](20260621_cycle_1.md)). Every variant was rejected under the pre-set 0.002 threshold and `candidate.py` was left unchanged. One cycle in one session, not a sustained overnight run |
| [`20260620_cycle_6_squad_player.md`](20260620_cycle_6_squad_player.md)† | Squad features (Transfermarkt XI value, age, league share) on 128 Copa América / AFCON / Asian Cup games: shuffled 5-fold CV log-loss 0.834 with them vs 0.813 Elo-only, no CI. The source has no World Cup or Euro lineups, so this is a limited-sample null. Its closing lines repeat a superseded market claim (section 4) |

Also: [`tier_1_completion.md`](tier_1_completion.md)† and [`tier_1_remediation.md`](tier_1_remediation.md) (Tier 1 data layer, secret hygiene, official FIFA 2026 tiebreak engine), [`cycle_2_scoreline_inplay.md`](cycle_2_scoreline_inplay.md) (Poisson / Dixon-Coles did not improve 1X2), [`approved_model_registry.md`](approved_model_registry.md)†, [`runtime_model_governance.md`](runtime_model_governance.md)†, [`tournament_simulator_known_limitations.md`](tournament_simulator_known_limitations.md).

**Machine-readable.** [`configs/approved_models.yaml`](../../configs/approved_models.yaml) is the runtime registry. It is governance-protected and still quotes the pre-erratum V8 numbers (E1). [`tiebreak_rules_2026.yaml`](../../data/reference/tiebreak_rules_2026.yaml).

**Tags.** `tier-1-complete`, `tier-1-baseline-recorded`, `approved-b1-runtime`.

### Market comparison

**Question.** Do bookmaker odds carry information beyond B1, and does a fixed B1/market blend improve on either?

**Verdict.** `positive-modest` for one fixed blend on one retrospective tournament, described by the note itself as "suggestive". It did not reappear in the 2026 prospective benchmark. The earlier cycle 4–5 claims are `superseded`.

**Sample.** 48 World Cup 2022 group matches, no-vig consensus odds about 94 minutes before kickoff, 2,000 resamples.

- The market alone had the best point RPS and log-loss (0.2244 / 1.0366 vs B1 0.2435 / 1.1217), but its CI vs B1 includes zero (dRPS −0.0191 [−0.046, +0.005]).
- Of three predeclared fixed blends, 75/25 B1/market was significant on RPS (dRPS −0.0067 [−0.013, −0.0005]) and on log-loss; 50/50 was significant on log-loss only.
- Eight intervals were reported with no multiplicity correction, and the upper bound of the RPS interval is −0.0005. No weight was selected and nothing was promoted. The development folds (2010/2014/2018) have no timestamp-valid odds, so the effect could not be checked there.
- On the 34 prospective 2026 fixtures the same 75/25 blend vs B1 gave an RPS delta of +0.0001 [−0.0044, +0.0042]. This is not a like-for-like replication: the 2026 market component is an early line, a median of about 98 hours before kickoff (errata E2), whereas the 2022 odds were taken about 94 minutes before kickoff.

| File | What it holds |
|---|---|
| [`market_shadow_evaluation_2022.md`](market_shadow_evaluation_2022.md) | The read-only 2022 shadow study, with its own strict caveats |
| [`odds_pilot_2022_md1_report.md`](odds_pilot_2022_md1_report.md) | Data-quality check of the 2022 odds (16 of 16 matchday-1 records strictly pre-kickoff; 0 credits spent) |
| [`odds_historical_pilot_v2_protocol.md`](odds_historical_pilot_v2_protocol.md), [`odds_historical_pilot_v2_results.md`](odds_historical_pilot_v2_results.md) | Six fixtures declared before retrieval, 20 of 30 credits used, diagnostic only |
| [`20260620_cycle_4.md`](20260620_cycle_4.md)†, [`20260620_cycle_5_true_alpha.md`](20260620_cycle_5_true_alpha.md)† | `superseded`. Early claims on 253–341 auxiliary internationals, 3 of 4 or 4 of 4 folds, no confidence intervals (errata E4) |

**Machine-readable.** None for the 2022 study (its outputs are gitignored). The prospective ledger is in the next section.

**Tags.** `shadow-session-20260621-closed` (2022 shadow study), `paid-source-activation-v1` (historical odds pilot v2), `tier-1-complete` (cycles 4–5).

### Prospective 2026 shadow evaluation

**Question.** On fixtures whose predictions were frozen before kickoff, can B1, the no-vig bookmaker consensus (`M2_market`, not to be confused with in-play M2), or a fixed B1/market blend (`M3_75_25`, `M4_50_50`, `M5_25_75`) be separated?

**Verdict.** `null`. Ledger classifications: B1 `reference_only`, `M2_market` `market_comparator_only`, all three blends `no_evidence_of_improvement`. Nothing was promoted.

**Sample.** 35 fixtures with frozen predictions (680 first-write-wins ledger rows); 34 scored, 1 excluded (`no_common_market_snapshot`). The lab's own label is Tier C, "exploratory" (20–49 fixtures). 5,000-resample match-level bootstrap.

| Model | RPS [95% CI] | Log-loss | Draw-Brier |
|---|---|---|---|
| B1 (`M1_B1`) | 0.1304 [0.0891, 0.1771] | 0.7754 | 0.1833 |
| `M2_market` (early line) | 0.1360 [0.0982, 0.1770] | 0.7740 | 0.1765 |

B1 is nominally better on RPS; the market is nominally better on log-loss and draw-Brier. Paired RPS delta, market minus B1: +0.0057 [−0.0118, +0.0226]. Zero of the 24 reported paired deltas (21 distinct comparisons) has a 95% CI excluding zero. The benchmark note concludes that there is no evidence that B1 or any blend improves on the market, or the reverse.

**Caveats.**

- **The market comparator is an early line, not a closing line.** For 31 of the 34 fixtures the primary snapshot is a 2026-06-21 baseline snapshot, a median of about 98 hours before kickoff (the other three: 2 final-pre-kickoff, 1 T-90). The cause is errata E2: a payload-key mismatch made the prediction freezer ignore all 47 later collector snapshots. The null therefore says nothing about B1 against a closing line.
- The snapshot-selection rule was pre-specified and outcome-independent, but it was written after the matches were played, and the ordering is self-attested: the rule, the script and the results share one commit.
- Group stage only; knockout rounds were never collected or scored.
- No frozen in-play model was ever scored prospectively.
- The collector's own score path was never patched; the independent harvester is the only working scoring path (errata E3).

| File | What it holds |
|---|---|
| [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](PROSPECTIVE_SHADOW_SCORECARD_V1.md)† | Per-model metrics with CIs and all paired deltas |
| [`PROSPECTIVE_MARKET_BENCHMARK_V1.md`](PROSPECTIVE_MARKET_BENCHMARK_V1.md)† | Snapshot-window and matchday strata, and the conclusion |
| [`prospective_score_harvest_preregistration.md`](prospective_score_harvest_preregistration.md) | The pre-specified (in-repo, self-attested) snapshot-selection rule |
| [`prospective_score_harvest_root_cause_audit.md`](prospective_score_harvest_root_cause_audit.md)† | Why the collector's scorer wrote empty scorecards with exit code 0 |
| [`PROSPECTIVE_SCORE_HARVEST_AND_BENCHMARK_V1_COMPLETION.md`](PROSPECTIVE_SCORE_HARVEST_AND_BENCHMARK_V1_COMPLETION.md)† | Capstone report: root cause, fix, counts, benchmark table, decision ledger |

Also: [`PROSPECTIVE_CALIBRATION_AND_RELIABILITY_V1.md`](PROSPECTIVE_CALIBRATION_AND_RELIABILITY_V1.md) (descriptive only, about 9 draws), [`prospective_score_deployment_decision.md`](prospective_score_deployment_decision.md) (why the collector patch was deferred), [`PROSPECTIVE_COLLECTION_ACTIVATION_REPORT.md`](PROSPECTIVE_COLLECTION_ACTIVATION_REPORT.md), [`final_2026_prospective_protocol.md`](final_2026_prospective_protocol.md), [`shadow_session_20260621_scorecard.md`](shadow_session_20260621_scorecard.md) (n=1, and a subset of the 34, so not additional evidence). Operator guide: [`docs/SCORE_HARVEST_GUIDE.md`](../../docs/SCORE_HARVEST_GUIDE.md).

**Machine-readable.** [`prospective_model_decision_ledger.json`](../../data/reference/prospective_model_decision_ledger.json) / [`.csv`](../../data/reference/prospective_model_decision_ledger.csv), [`prospective_frozen_input_manifest.json`](../../data/reference/prospective_frozen_input_manifest.json) / [`.csv`](../../data/reference/prospective_frozen_input_manifest.csv), [`prospective_score_harvest_failure_matrix.json`](../../data/reference/prospective_score_harvest_failure_matrix.json) (14 candidate causes), [`future_2026_prospective_queue.csv`](../../data/reference/future_2026_prospective_queue.csv).

**Tags.** `shadow-session-20260621-closed`, `v1-5-prospective-readiness`, `shadow-offline-hardening-v1`, `prospective-score-harvest-benchmark-v1`.

### In-play models

**Question.** Does updating a forecast with the live score and clock improve on the pre-match forecast? Does anything richer improve on a simple remaining-time Poisson model (in-play M2: unfitted, hand-set constants, base goal rate 1.35 and Elo coefficient 0.20)?

**Verdict.**

- `positive-modest`, in-play vs static: any score-and-time-aware update improves on a static pre-match forecast. On 30 finished 2026 matches (519 rows) the pre-specified M1 scored RPS 0.1478 vs 0.1897 for static M0. The match-level paired bootstrap gives dRPS −0.0447, 95% CI [−0.084, −0.005]; it averages per-match means, so it differs slightly from the row-level RPS gap. The repo labels these 30 matches "exploratory, NOT pristine" because they were seen during development, so the magnitude is indicative only.
- `positive-modest`, **not confirmed**, simple Poisson vs fitted baseline: on 151 group matches from 5 tournaments (leave-one-competition-out) the unfitted M2 improved on the fitted M1 on 5 of 5 held-out competitions (RPS 0.127 vs 0.142, dRPS −0.0145 [−0.021, −0.008]). On the later, larger, overlapping 302-match set the gain was not significant (nested selection vs M1: dRPS −0.0042 [−0.0083, +0.0002]).
- `null` for everything richer than M2: six xG feature families, team-state and lineup-continuity models, and player-state candidates showed no evidence of improvement at these sample sizes (details in the files below and in the next section). Market-anchored M6 vs Elo-anchored M2: no significant difference (dRPS −0.0004 [−0.008, +0.007]).
- `superseded`: "M2fit_temp is the best in-play model" was a selection-on-test artifact. Under nested evaluation it was never selected (plain M2 in 4 of 6 folds, M5 in 2 of 6).
- Dynamic phase (627 internationals, 3,135 forward-chained snapshots): 0 candidates promoted. A mis-scoring that had falsely flagged baseline R1 as a candidate was caught and corrected.

No frozen in-play model was ever scored prospectively. The freeze manifests are governance machinery, not an evaluated result.

**Provenance caveat.** The 151-match note records that part of its AFCON fold and all 10 of its Asian Cup matches were fetched with a second free API-Football account, which the provider suspended mid-fetch. The note states that no further free accounts would be created; later corpus work used a single paid plan. The Asian Cup fold is therefore partial (10 of 36 matches).

| File | What it holds |
|---|---|
| [`inplay_evaluation_reconciliation.md`](inplay_evaluation_reconciliation.md) | The audit that caught selection-on-test, and which claims still stand |
| [`inplay_nested_evaluation.md`](inplay_nested_evaluation.md), [`inplay_model_selection_report.md`](inplay_model_selection_report.md) | Nested leave-one-competition-out on 302 StatsBomb internationals (6 tournaments, 5,738 rows, no 2026 data) |
| [`inplay_multicompetition_results.md`](inplay_multicompetition_results.md) † | The 151-match study, including the provenance caveat above. Its "shadow-candidate" verdict for M2 and M6 is `superseded` (section 4) |
| [`event_replay_2022_remediation.md`](event_replay_2022_remediation.md), [`event_replay_2022_release_gate.md`](event_replay_2022_release_gate.md) | The own-goal inversion bug (Canada 1–2 Morocco had been derived as 0–3) and the provider-aware fix: 48 of 48 cached 2022 group matches reconcile, up from 47 |
| [`DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md`](DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md) | The 627-match dynamic phase and its decision ledger |

Also: [`tier_4_sprint_1_completion.md`](tier_4_sprint_1_completion.md) (48 matches / 858 rows; only the M5 ensemble improved on M1 with match-level significance; goal-within-5-minutes hazard did not improve on its base rate, Brier 0.1148 vs 0.1126), [`DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION.md`](DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION.md) (team-state and lineup-continuity models did not improve on the Poisson reference; club→international transfer neutral), [`inplay_2026_holdout.md`](inplay_2026_holdout.md)† (headline `superseded`), [`model_namespace_reconciliation.md`](model_namespace_reconciliation.md) (the two "M2"s). Protocol: [`docs/INPLAY_EVALUATION_PROTOCOL.md`](../../docs/INPLAY_EVALUATION_PROTOCOL.md).

**Machine-readable.** [`inplay_result_status_registry.yaml`](inplay_result_status_registry.yaml) (validity label per claim), [`final_holdout_freeze_manifest.json`](final_holdout_freeze_manifest.json) (v1, kept as an immutable record) and [`final_holdout_freeze_manifest_v2.json`](final_holdout_freeze_manifest_v2.json) (re-freeze to plain M2), [`model_decision_ledger.json`](../../data/reference/model_decision_ledger.json) / [`.csv`](../../data/reference/model_decision_ledger.csv) (dynamic phase).

**Tags.** `event-replay-2022-validated`, `tier-4-research-sprint-1`, `evaluation-reset-event-expansion`, `deep-research-inplay-foundation-v1`, `dynamic-inplay-intelligence-v1`.

### Player and xG plane

**Question.** Do lineups, player history, substitutions or expected-goals (xG) state add anything to Elo (pre-match) or to the score-and-time reference (in-play)?

**Verdict.**

- `negative` (pre-match): on 166 usable matches, leave-one-competition-out, Elo plus starting-XI strength scored RPS 0.2148 vs 0.2126 for Elo only (dRPS +0.0022 [+0.000, +0.005], worse). Key-player availability was not significant.
- `null` (xG): six xG feature families fixed before testing, 302 matches, all non-significant (all-xG RPS 0.1531 vs 0.1528; dRPS +0.0002 [−0.001, +0.002]).
- `incomplete` (first in-play player-impact sprint): its results table was identical to the prior sprint's because the job script mapped P1–P4 onto inherited predictors, and only 60 of 2,000 planned player-history fixtures had been pulled. The lab's own claim ledger downgraded it to `incomplete_or_partial` / needs rerun.
- `rejected` (the full-corpus rerun, 627 internationals): player candidates P1–P5 scored pooled forward-chain RPS of about 0.149–0.152 vs 0.1523 for the reference. All five failed the rules fixed beforehand (match-level bootstrap CI, draw calibration, fold consistency). xG candidates X1 and X3 were `rejected` and X2 kept `reference_only`; they were scored on a different, easier 258-match subset, so their raw RPS is not comparable.

| File | What it holds |
|---|---|
| [`player_plane_results.md`](player_plane_results.md) | The pre-match player-feature negative |
| [`inplay_xg_preregistered_results.md`](inplay_xg_preregistered_results.md) | Per-family xG deltas with CIs. The note states that the six families were fixed in code before testing (in-repo, self-attested) |
| [`research_claim_verification_ledger.md`](research_claim_verification_ledger.md), [`research_truth_registry_report.md`](research_truth_registry_report.md) | The rescan of actual raw files that downgraded the first player-impact result |
| [`PLAYER_IMPACT_XG_FUSION_COMPLETION.md`](PLAYER_IMPACT_XG_FUSION_COMPLETION.md)† | The first sprint. Its P1–P4 table is `superseded`; do not quote it |
| [`RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION.md`](RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION.md) | A sprint that declared itself INCOMPLETE and withheld its completion tag because hard gates were false at the time |

Also: [`complete_xg_snapshot_join_report.md`](complete_xg_snapshot_join_report.md) (4,386 snapshots over 258 matches; its cache claim was later contradicted, see section 4), [`PLAYER_IMPACT_XG_PREREGISTRATION.md`](PLAYER_IMPACT_XG_PREREGISTRATION.md), [`inplay_player_state_preregistration_v1.md`](inplay_player_state_preregistration_v1.md), [`player_history_data_card.md`](player_history_data_card.md), [`xg_event_state_data_card.md`](xg_event_state_data_card.md). The rerun is reported in [`DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md`](DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md).

**Machine-readable.** [`research_truth_registry.json`](../../data/reference/research_truth_registry.json), [`model_decision_ledger.json`](../../data/reference/model_decision_ledger.json), [`xg_snapshot_join_audit.json`](../../data/reference/xg_snapshot_join_audit.json), [`player_history_corpus_manifest.json`](../../data/reference/player_history_corpus_manifest.json).

**Tags.** `player-impact-xg-fusion-v1`, `research-truth-full-corpus-xg-fusion-incomplete` (the tag name is literal), `dynamic-inplay-intelligence-v1`, `evaluation-reset-event-expansion`.

### API-Football corpus and providers

**Question.** Can a paid, quota-limited provider supply a governed event and lineup corpus, and which licensed provider could fill the remaining gaps?

**Verdict.** This is data engineering, so there is no model verdict. Per-shot xG and shot location are `data_insufficient` at the provider level, based on a sampled audit.

**Sample and results.**

- Event-derived regulation scores matched the provider's own full-time score on all 900 audited fixtures (627 international + 273 club), and on 1,120 of 1,120 after a predeclared 220-fixture extension. This is an internal-consistency check against the same provider. It is not claimed for the full 2,000-fixture player-history pull.
- The fixture manifest was committed before the corpus backfill retrieved events or lineups, so inclusion depended on metadata only.
- The own-goal inversion bug from the in-play line resurfaced in a second module (12 of 120 mismatches, then 120 of 120 after the fix).
- A backfill reported 2,000 of 2,000 but only 1,940 fixtures were raw-backed in the canonical root. The gate was changed to measure actual raw-backed coverage.
- Sampled provider audit (27 requests): statistics are team-level with no per-shot coordinates; xG was present in the sampled Euro 2024 fixture and absent in the sampled World Cup 2022 fixture.
- Provider decision matrix (5 vendors, public pages only, nothing purchased or contacted): usage rights and historical depth, not coverage, are the binding unknowns.

| File | What it holds |
|---|---|
| [`API_FOOTBALL_HISTORICAL_CORPUS_COMPLETION.md`](API_FOOTBALL_HISTORICAL_CORPUS_COMPLETION.md) | Budget use, the 900-fixture reconciliation, readiness counts per model class (data-volume counts, not model results) |
| [`api_football_reconciliation_remediation.md`](api_football_reconciliation_remediation.md) | The own-goal root cause and the release rule: reconcile exactly, or classify and exclude |
| [`api_football_corpus_sampling_protocol.md`](api_football_corpus_sampling_protocol.md) | Metadata-only fixture selection and the quota budget formula |
| [`RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md`](RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md) | An operations log that contains a real finding: the over-reported 2,000 / 2,000 coverage claim and its fix |
| [`structured_event_provider_decision_matrix.md`](structured_event_provider_decision_matrix.md) | Five providers compared on price transparency, xG depth, rights clarity and integration cost. It recommends no single provider. The earlier [`data_provider_decision_package.md`](data_provider_decision_package.md) had named Sportmonks as the lowest-cost path; read the later matrix as the current position |

Also: [`api_football_empirical_coverage_audit.md`](api_football_empirical_coverage_audit.md), [`PAID_SOURCE_ACTIVATION_COMPLETION.md`](PAID_SOURCE_ACTIVATION_COMPLETION.md), [`live_provider_truth_audit.md`](live_provider_truth_audit.md) (resolves the free-tier vs Pro-plan contradiction in earlier notes), [`source_readiness_audit.md`](source_readiness_audit.md), [`api_football_red_threshold_extension_protocol.md`](api_football_red_threshold_extension_protocol.md), [`STRUCTURED_EVENT_PROCUREMENT_READINESS_COMPLETION.md`](STRUCTURED_EVENT_PROCUREMENT_READINESS_COMPLETION.md).

**Machine-readable.** [`api_football_corpus_fixture_manifest.json`](../../data/reference/api_football_corpus_fixture_manifest.json), [`api_football_empirical_coverage.json`](../../data/reference/api_football_empirical_coverage.json), [`corpus_coverage_ledger.json`](../../data/reference/corpus_coverage_ledger.json) (the current coverage record; several other manifests are stale snapshots, errata E7), [`canonical_counts_ledger.json`](../../data/reference/canonical_counts_ledger.json), [`structured_event_provider_catalog.json`](../../data/reference/structured_event_provider_catalog.json).

**Tags.** `data-readiness-gate-1`, `paid-source-activation-v1`, `api-football-historical-corpus-v1`, `structured-event-procurement-readiness-v1`.

### Event-process intelligence

**Question.** Do possession, territory, transition, pressure, set-piece and chance-quality features derived from event data improve in-play forecasts over the remaining-time Poisson reference (called e2 in this line)?

**Verdict.** `reference_only` ×20, `data_insufficient` ×2, 0 candidates. On the 58-match international cohort every e3–e9 model had a worse leave-one-competition-out RPS than the reference (0.1496). The lab's own power analysis calls this sample underpowered, so read it as no evidence of improvement at this sample size.

| File | What it holds |
|---|---|
| [`EVENT_PROCESS_INTELLIGENCE_V1_COMPLETION.md`](EVENT_PROCESS_INTELLIGENCE_V1_COMPLETION.md) | What was built (engine, snapshot datasets, 669-file club auxiliary corpus) and the verdict counts |
| [`event_process_scientific_report_draft.md`](event_process_scientific_report_draft.md) | Question, protocol, RPS table, limitations |
| [`domain_event_process_inventory_report.md`](domain_event_process_inventory_report.md) | Inventory of event-process data by domain |

**Machine-readable.** [`event_process_model_decision_ledger.json`](../../data/reference/event_process_model_decision_ledger.json) / [`.csv`](../../data/reference/event_process_model_decision_ledger.csv), [`event_process_auxiliary_manifest.json`](../../data/reference/event_process_auxiliary_manifest.json), [`statsbomb_event_process_catalog.json`](../../data/reference/statsbomb_event_process_catalog.json).

**Tag.** `event-process-intelligence-v1`.

### Residual goal intensity

**Question.** If the Poisson model is treated as a reference intensity, can a learned residual correction, applied selectively, improve on it?

**Verdict.** `reference_only` ×7, `rejected` ×6, `data_insufficient` ×3, 0 candidates. On 58 matches (7,376 snapshots, with the match as the bootstrap unit) the reference R0 had the best pooled forward-chain RPS (0.15263). The selective-correction model scored 0.15767. With 58 matches this is an underpowered test, so read it as no evidence of improvement at this sample size.

| File | What it holds |
|---|---|
| [`RESIDUAL_GOAL_INTENSITY_V1_COMPLETION.md`](RESIDUAL_GOAL_INTENSITY_V1_COMPLETION.md) | Datasets, evaluation and the decision ledger summary |
| [`residual_goal_intensity_scientific_report_draft.md`](residual_goal_intensity_scientific_report_draft.md) | Short question / protocol / result / limitations write-up |
| [`residual_58_match_audit.md`](residual_58_match_audit.md) | Why only 58 matches, and the from-scratch recompute of R0 |
| [`residual_feature_catalog.md`](residual_feature_catalog.md), [`residual_regime_coverage_report.md`](residual_regime_coverage_report.md) | Feature list and regime coverage |

**Machine-readable.** [`residual_goal_intensity_decision_ledger.json`](../../data/reference/residual_goal_intensity_decision_ledger.json) / [`.csv`](../../data/reference/residual_goal_intensity_decision_ledger.csv), [`residual_58_match_cohort.csv`](../../data/reference/residual_58_match_cohort.csv), [`residual_58_match_audit.json`](../../data/reference/residual_58_match_audit.json).

**Tag.** `residual-goal-intensity-v1`.

### Evidence, power and cohort lineage

**Question.** Why were only 58 of 258 bridged matches evaluated, are the reported numbers reproducible, and what could that sample detect?

**Verdict.** Methodological; there is no model verdict. Findings:

- Cohort lineage 298 → 258 → 58 with every drop reasoned. The 200-match drop was missing event files on disk, not a modelling rule. The earlier "258 cached" claim is marked `contradicted` in the lab's own evidence registry.
- An internal from-scratch recompute of the unfitted reference matched the reported RPS (0.15263 forward-chain, 0.14906 leave-one-competition-out). Only the reference was recomputed, not any fitted candidate. Of seven major evaluations, the internal reproducibility audit rates 1 `reproducible_verified`, 5 with limitations and 1 `needs_rerun`.
- The match is the independent unit: inflating snapshots 1×/2×/4×/8× on the same 58 matches left power flat.
- The 58-match projection (power 0.49 for a 0.005 absolute RPS gain, about 150 matches for 80% power) used an optimistic noise template and is `superseded`. On the 231-match event lake, power for that gain is 0.28, and 80% power first appears at the 1,200-match grid point.

| File | What it holds |
|---|---|
| [`match_level_power_analysis.md`](match_level_power_analysis.md)† | The match-clustered power analysis. Its "Why 58" section still says the 258 matches were on disk; that wording is superseded |
| [`residual_58_match_audit.md`](residual_58_match_audit.md) | The funnel and the recompute |
| [`evaluation_cohort_lineage_report.md`](evaluation_cohort_lineage_report.md) | Match-level lineage with one allowed drop reason per transition |
| [`research_evidence_registry_report.md`](research_evidence_registry_report.md) | Ten artifact records with claim status (1 contradicted, 1 incomplete) |
| [`evaluation_reproducibility_audit.md`](evaluation_reproducibility_audit.md) | The seven-evaluation reproducibility classification |

Also: [`EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md`](EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md), [`minimum_evidence_requirements.md`](minimum_evidence_requirements.md) (`superseded` thresholds), [`EVIDENCE_POWER_DECISION_MEMO.md`](EVIDENCE_POWER_DECISION_MEMO.md), [`NEXT_INVESTMENT_DECISION_MEMO.md`](NEXT_INVESTMENT_DECISION_MEMO.md) (its "0.49 → >0.8" projection did not hold).

**Machine-readable.** [`international_event_lake_power_analysis.md`](../../data/reference/international_event_lake_power_analysis.md) (the current power estimate), [`match_level_power_analysis.json`](../../data/reference/match_level_power_analysis.json), [`minimum_evidence_requirements.json`](../../data/reference/minimum_evidence_requirements.json), [`evaluation_cohort_lineage.json`](../../data/reference/evaluation_cohort_lineage.json), [`cohort_exclusion_ledger.json`](../../data/reference/cohort_exclusion_ledger.json), [`research_evidence_registry.json`](../../data/reference/research_evidence_registry.json), [`evaluation_reproducibility_audit.json`](../../data/reference/evaluation_reproducibility_audit.json), [`live_readiness_matrix.json`](../../data/reference/live_readiness_matrix.json).

**Tag.** `evidence-power-consolidation-v1`.

### International event lake

**Question.** After restoring all 258 StatsBomb Open Data event files into a hash-verified store, does rerunning the locked model families on the larger cohort change any verdict?

**Verdict.** `reference_only` for all 10 model records (the reference e2 plus 9 other models), on 231 model-eligible matches after 27 exclusions. Read this as no evidence of improvement at this sample size: the lab's own power analysis puts power for a 0.005 RPS gain at 0.28 on 231 matches.

**Two things to know before quoting this line.**

- Model e9 had a lower leave-one-competition-out RPS than the reference (0.13358 vs 0.14034, CI excluding zero) but **failed** the locked multi-rule gate: its log-loss was worse (0.8226 vs 0.7463) and its forward-chain RPS was not better. It stayed `reference_only`. It is not a positive result.
- The completion report prints "Verdict: data_insufficient / Reference: None". That is a packaging default. The per-model ledger records 10 `reference_only` against reference e2. Both describe the same outcome: nothing improved on the reference (errata E6).

The lake itself (258 of 258 objects hash-verified; 58 copied locally, 200 retrieved from the official source) lives on the author's disk and is not redistributed.

| File | What it holds |
|---|---|
| [`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md`](INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md)† | Completion report: cohort, integrity, provenance |
| [`international_event_lake_data_contract.md`](international_event_lake_data_contract.md) | Scope, source rules and guarantees of the content-addressed store |
| [`legacy_statsbomb_cache_restoration_protocol.md`](legacy_statsbomb_cache_restoration_protocol.md) | The copy-if-verified, otherwise retrieve-from-official-source rule |
| [`official_modern_international_catalog_report.md`](official_modern_international_catalog_report.md), [`expanded_international_bridge_report.md`](expanded_international_bridge_report.md) | The 333-match official catalog and the strict exact bridge |
| [`international_event_lake_audit_report.md`](international_event_lake_audit_report.md) | A pre-acquisition snapshot showing 59 objects. It is stale by design; the completion report has the final 258 |

**Machine-readable.** [`international_event_lake_model_decision_ledger.json`](../../data/reference/international_event_lake_model_decision_ledger.json) / [`.csv`](../../data/reference/international_event_lake_model_decision_ledger.csv) (rule-by-rule adjudication), [`international_event_lake_power_analysis.md`](../../data/reference/international_event_lake_power_analysis.md) / [`.json`](../../data/reference/international_event_lake_power_analysis.json), [`international_event_lake_minimum_evidence_requirements.json`](../../data/reference/international_event_lake_minimum_evidence_requirements.json), [`international_event_lake_cohort_manifest.json`](../../data/reference/international_event_lake_cohort_manifest.json), [`international_event_lake_cohort_exclusions.csv`](../../data/reference/international_event_lake_cohort_exclusions.csv), [`international_event_lake_cohort_report.md`](../../data/reference/international_event_lake_cohort_report.md).

**Tag.** `international-event-lake-restoration-v1`.

### Hierarchical transfer

**Question.** Does club-football event data help international in-play forecasts through pooling or selective transfer?

**Verdict.** `incomplete` and `untested`. No model improved on the reference T0 (4 forward-chain folds, 194 held-out international test matches). The run had **0 club training rows**, so five of the seven candidates scored identically and cross-domain lift was never exercised. One pipeline defect was repaired (club root, 0 → 669 files); a second was diagnosed and not repaired. The decision ledger that the completion report cites was cleared during that unfinished repair and never regenerated (errata E5). There is no git tag.

| File | What it holds |
|---|---|
| [`HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md`](HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md)† | The results table and the statement that cross-domain lift is UNTESTED and not claimed |
| [`hierarchical_transfer_club_root_repair.md`](hierarchical_transfer_club_root_repair.md) | The defect that produced zero club rows, and its repair |
| [`domain_shift_and_feature_stability_report.md`](domain_shift_and_feature_stability_report.md) | Cross-domain overlap audit, reported as `data_insufficient` instead of fabricated |
| [`HIERARCHICAL_TRANSFER_DEPENDENCY_STATUS.md`](HIERARCHICAL_TRANSFER_DEPENDENCY_STATUS.md) | What the run depended on |

**Machine-readable.** [`hierarchical_transfer_repair_log.json`](../../data/reference/hierarchical_transfer_repair_log.json), [`hierarchical_feature_stability_registry.json`](../../data/reference/hierarchical_feature_stability_registry.json), [`domain_normalized_transfer_audit.json`](../../data/reference/domain_normalized_transfer_audit.json). **Do not quote** [`hierarchical_transfer_eval_audit.json`](../../data/reference/hierarchical_transfer_eval_audit.json): its `dataset` field is `synthetic_self_test`.

**Tag.** None (branch work only).

### Commentary NLP

**Question.** Can broadcast commentary transcripts be turned into event labels precise enough to use as training data? This line uses European **club** football; it never touched the World Cup or any forecast in this repository.

**Verdict.** `negative`. 383,591 SoccerNet-Echoes ASR segments, 254 English-translated club games, 6 leave-one-competition-out folds. Under a gate fixed before fitting (at least 50 emissions, Wilson 95% lower bound on precision ≥ 0.80, timing and fold stability), **0 of 12 event classes qualified** and the silver-label dataset was released empty. Closest: corner precision 0.786 (Wilson lower bound 0.768, n = 2,129) and foul 0.788 (lower bound 0.768).

Other results: abstention raised goal precision from 0.15 to 0.67 only by cutting emitted labels from 9,860 to 76. English keyword rules fail on untranslated Spanish ASR (goal recall 0.8846 → 0.0535 on the La Liga fold). None of 8 assessed commentary sources passed the fail-closed live-eligibility gate, because none carries publication timestamps. No outcome model was trained and no predictive value is claimed.

The repository tracks no commentary text and no SoccerNet label files, only manifests and aggregates.

| File | What it holds |
|---|---|
| [`COMMENTARY_PRECISION_V2_COMPLETION.md`](COMMENTARY_PRECISION_V2_COMPLETION.md) | Best single read: data volume, protocol, per-class results, the recommendation to stop investing in this source |
| [`COMMENTARY_PRECISION_PREREGISTRATION.md`](COMMENTARY_PRECISION_PREREGISTRATION.md) | The thresholds, committed in-repo before the model code and results (self-attested) |
| [`commentary_silver_label_release_gate.md`](commentary_silver_label_release_gate.md) | The per-class gate decision table |
| [`commentary_precision_outer_fold_results.md`](commentary_precision_outer_fold_results.md), [`commentary_precision_failure_analysis.md`](commentary_precision_failure_analysis.md) | Per-fold numbers and why every class failed |
| [`soccernet_real_alignment_evaluation.md`](soccernet_real_alignment_evaluation.md) | Baseline keyword-and-time alignment and the language-dependence result. Its "stable across folds" sentence is contradicted by the later failure analysis |

Also: [`commentary_live_readiness_gate.md`](commentary_live_readiness_gate.md), [`commentary_source_rights_audit.md`](commentary_source_rights_audit.md), [`commentary_downstream_utility_verdict.md`](commentary_downstream_utility_verdict.md), [`soccernet_match_mapping_quality.md`](soccernet_match_mapping_quality.md), [`SOCCERNET_REAL_ALIGNMENT_COMPLETION.md`](SOCCERNET_REAL_ALIGNMENT_COMPLETION.md), [`COMMENTARY_INTELLIGENCE_RESEARCH_COMPLETION.md`](COMMENTARY_INTELLIGENCE_RESEARCH_COMPLETION.md), [`commentary_low_confidence_signals_report.md`](commentary_low_confidence_signals_report.md) (the fallback after the gate failed: 2,710 corner, foul and yellow-card records explicitly flagged as low-confidence and non-silver; the records themselves are gitignored).

**Machine-readable.** [`commentary_silver_label_gate.json`](commentary_silver_label_gate.json) (in this directory), [`soccernet_language_and_fold_comparison.json`](soccernet_language_and_fold_comparison.json), [`commentary_source_catalog.json`](../../data/reference/commentary_source_catalog.json), [`soccernet_action_label_catalog.json`](../../data/reference/soccernet_action_label_catalog.json).

**Tags.** `commentary-intelligence-research-v1`, `soccernet-real-alignment-v1`, `commentary-precision-weak-supervision-v2`, `commentary-low-confidence-signals-v1`.

### Cross-cutting notes

| File | What it holds |
|---|---|
| [`model_namespace_reconciliation.md`](model_namespace_reconciliation.md) | Why `M2` means two different models, and the namespaced alias registry that resolves it |
| [`program_model_registry.md`](program_model_registry.md)† | One list of every model and its status. Its main table still has a superseded in-play row; the correction sits in a section below it |
| [`security_remediation.md`](security_remediation.md) | Secret-hygiene remediation (2026-06-20), done before the first commit. The tracked `.env.example` has only ever been committed with blank key fields (one commit, `e78cde4`). This supersedes the stale line in [`tier_1_data_card.md`](tier_1_data_card.md) that says the file "still holds real keys" |
| [`provenance_policy.md`](provenance_policy.md) | Per-record provenance envelope and raw-storage rules |
| [`wcdrawlab_building_block_map.md`](wcdrawlab_building_block_map.md) | Module-by-module map of the `wcdrawlab` package |

## Superseded or corrected claims

These claims are still visible in the files listed, because the original text is kept. Files marked † carry a dated banner above that text; for the others, this table is the correction. Full detail is in [`docs/ERRATA.md`](../../docs/ERRATA.md).

| Claim | Where it appears | What supersedes it |
|---|---|---|
| A market-plus-Elo blend scored better than the no-vig consensus and the Pinnacle closing line by about 4–7% RPS, described as "real" predictive signal | [`20260620_cycle_4.md`](20260620_cycle_4.md)†, [`20260620_cycle_5_true_alpha.md`](20260620_cycle_5_true_alpha.md)†; echoed in [`20260620_cycle_6_squad_player.md`](20260620_cycle_6_squad_player.md)†, [`tier_1_completion.md`](tier_1_completion.md)†, [`current_repository_state.md`](current_repository_state.md)† | [Errata E4](../../docs/ERRATA.md#e4--early-beats-the-market-notes-were-never-confirmed). 253–341 auxiliary internationals, 3 of 4 or 4 of 4 folds, no confidence intervals. Reclassified "valid but auxiliary" in [`model_state_reconciliation.md`](model_state_reconciliation.md)†. Not confirmed prospectively: [`PROSPECTIVE_MARKET_BENCHMARK_V1.md`](PROSPECTIVE_MARKET_BENCHMARK_V1.md)† (34 fixtures, early-line market comparator). This repository does not claim to improve on any market |
| "M2fit_temp is the best in-play model" | [`inplay_2026_holdout.md`](inplay_2026_holdout.md)†, [`inplay_xg_results.md`](inplay_xg_results.md)†, main table of [`program_model_registry.md`](program_model_registry.md)†, [`final_holdout_freeze_manifest.json`](final_holdout_freeze_manifest.json) (v1 freeze) | Selection on the test set. [`inplay_evaluation_reconciliation.md`](inplay_evaluation_reconciliation.md), [`inplay_nested_evaluation.md`](inplay_nested_evaluation.md), [`inplay_result_status_registry.yaml`](inplay_result_status_registry.yaml); re-freeze to plain M2 in [`final_holdout_freeze_manifest_v2.json`](final_holdout_freeze_manifest_v2.json) |
| The V8 candidate was clearly worse than B1 on the 33-match 2026 prequential, but far better on draw calibration | [`prequential_2026.md`](prequential_2026.md)†, [`approved_model_registry.md`](approved_model_registry.md)†, [`runtime_model_governance.md`](runtime_model_governance.md)†, [`OVERNIGHT_FINAL_REPORT.md`](OVERNIGHT_FINAL_REPORT.md)†, [`model_state_reconciliation.md`](model_state_reconciliation.md)† ("reproduced within tolerance"), and [`configs/approved_models.yaml`](../../configs/approved_models.yaml) | [Errata E1](../../docs/ERRATA.md#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug). A bug zero-filled every candidate feature, so V8 emitted near-constant forecasts. Corrected on the same 33 matches: V8 RPS 0.173 / log-loss 0.948 / draw-cal 0.175 vs B1 0.174 / 0.958 / 0.178, which is a tie. B1's figures were never affected. V8 remains shadow-only for the valid reason: no significant dev-fold improvement |
| All 258 StatsBomb event files are cached, and the 58-match cohort was a "build-time cap" | [`statsbomb_full_event_cache_report.md`](statsbomb_full_event_cache_report.md), [`complete_xg_snapshot_join_report.md`](complete_xg_snapshot_join_report.md), "Why 58" in [`match_level_power_analysis.md`](match_level_power_analysis.md)†, [`NEXT_INVESTMENT_DECISION_MEMO.md`](NEXT_INVESTMENT_DECISION_MEMO.md), [`statsbomb_cache_audit.json`](../../data/reference/statsbomb_cache_audit.json) | About 60 files were on disk when checked. Marked `contradicted` in [`research_evidence_registry_report.md`](research_evidence_registry_report.md); funnel in [`residual_58_match_audit.md`](residual_58_match_audit.md); restored to 258 of 258 in an external store per [`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md`](INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md)† |
| First player-impact sprint: "P2 ties the reference at RPS 0.150", so player-impact features were tested and rejected | [`PLAYER_IMPACT_XG_FUSION_COMPLETION.md`](PLAYER_IMPACT_XG_FUSION_COMPLETION.md)† | The table was identical to the prior sprint's because P1–P4 were mapped onto inherited predictors, and only 60 of 2,000 planned fixtures had been pulled. Downgraded in [`research_claim_verification_ledger.md`](research_claim_verification_ledger.md). The valid rerun is in [`DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md`](DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md) and promoted nothing |
| About 150 matches give 80% power for a 0.005 RPS gain; materialising 258 matches lifts power "from 0.49 to >0.8" | [`match_level_power_analysis.md`](match_level_power_analysis.md)†, [`minimum_evidence_requirements.md`](minimum_evidence_requirements.md), [`NEXT_INVESTMENT_DECISION_MEMO.md`](NEXT_INVESTMENT_DECISION_MEMO.md), [`EVIDENCE_POWER_DECISION_MEMO.md`](EVIDENCE_POWER_DECISION_MEMO.md) | The 58-match estimate used a noise template from a candidate that was identical to the reference on most matches. Re-estimated on 231 matches: power 0.28, and 80% power first at the 1,200-match grid point. [`international_event_lake_power_analysis.md`](../../data/reference/international_event_lake_power_analysis.md) |
| In-play M2 and M6 are "shadow-candidates" that pass | [`inplay_multicompetition_results.md`](inplay_multicompetition_results.md) †, [`RESUME_NEXT_TASK.md`](RESUME_NEXT_TASK.md)† | Not confirmed at significance on the 302-match set ([`inplay_nested_evaluation.md`](inplay_nested_evaluation.md)). No in-play model was ever scored prospectively |
| Own goals are "credited to the opponent" | [`api_football_2022_replay_report.md`](api_football_2022_replay_report.md)† | That was the bug. API-Football's `team` field on an own goal is already the beneficiary: [`event_replay_2022_remediation.md`](event_replay_2022_remediation.md), [`api_football_reconciliation_remediation.md`](api_football_reconciliation_remediation.md) |
| Player-history corpus 3% complete, StatsBomb cache 23%, 0 snapshots joined; later "2,000 / 2,000 complete" | [`RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION.md`](RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION.md), [`research_truth_registry_report.md`](research_truth_registry_report.md), [`RESEARCH_TRUTH_FUSION_STATE.yaml`](RESEARCH_TRUTH_FUSION_STATE.yaml) | Both were true on the day. The 2,000 / 2,000 claim over-reported (1,940 raw-backed in the canonical root) and was caught in [`RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md`](RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md). Current record: [`corpus_coverage_ledger.json`](../../data/reference/corpus_coverage_ledger.json) ([errata E7](../../docs/ERRATA.md#e7--stale-manifests-and-machine-specific-paths)) |
| Event-lake verdict "data_insufficient / Reference: None" | [`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md`](INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md)† | [Errata E6](../../docs/ERRATA.md#e6--two-vocabularies-for-the-same-event-lake-outcome). A packaging default. The per-model ledger records 10 `reference_only`: [`international_event_lake_model_decision_ledger.json`](../../data/reference/international_event_lake_model_decision_ledger.json) |
| The hierarchical-transfer run is "complete" and its decision ledger is at `data/reference/hierarchical_transfer_decision_ledger.json` | [`HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md`](HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md)† | [Errata E5](../../docs/ERRATA.md#e5--the-hierarchical-transfer-decision-ledger-is-missing). That ledger is not in the repository: it was cleared during an unfinished repair and never regenerated. The run had 0 club training rows, so the result is null and cross-domain transfer is untested. See [Hierarchical transfer](#hierarchical-transfer) |
| The root-cause audit ruled out "snapshot parsing" as a cause of the scoring failure | [`prospective_score_harvest_root_cause_audit.md`](prospective_score_harvest_root_cause_audit.md)† | [Errata E2](../../docs/ERRATA.md#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger). A key mismatch between the odds fetcher and the freezer meant all 47 durable-collector snapshots were silently ignored. The benchmark's market is therefore an early line (31 of 34 fixtures, median about 98 hours before kickoff), not a closing line |
| Prospective benchmark is "Tier A, 0 finalized eligible matches" | [`prospective_review_gate.md`](prospective_review_gate.md) | Written before the harvest. Final state: 34 scored, Tier C ("exploratory"), against an early-line market comparator, in [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](PROSPECTIVE_SHADOW_SCORECARD_V1.md)† |
| API-Football is blocked, or limited to the free tier's 2022–2024 seasons | Many early notes, including [`api_football_diagnostic.md`](api_football_diagnostic.md), [`PROGRAM_CURRENT_TRUTH.md`](PROGRAM_CURRENT_TRUTH.md)†, [`OVERNIGHT_FINAL_REPORT.md`](OVERNIGHT_FINAL_REPORT.md)† | [`live_provider_truth_audit.md`](live_provider_truth_audit.md): the account moved to the paid Pro plan, and the free-tier notes are historical |
| Test pass counts (45, 51, 61, 151, 324, 451, 601 …) | Completion reports and audits throughout | Point-in-time only. Verified on 2026-09-20 under fresh-clone conditions: 817 passed, 51 skipped, 0 failed. The skips need gitignored data: [`docs/TESTING_AND_DATA_DEPENDENCIES.md`](../../docs/TESTING_AND_DATA_DEPENDENCIES.md) |

## Operating-state files

About a third of this directory (102 of 325 files) is not research. It is the control-loop state that the AI agent wrote so that a long-running sprint could be stopped and resumed: what it was doing, what was queued, what was blocked, and its own attestations that it had not touched the live collector.

These files are useful as a record of how the agent was governed. They are not findings, and several are stale relative to the completion reports. For example, [`HIERARCHICAL_TRANSFER_STATE.yaml`](HIERARCHICAL_TRANSFER_STATE.yaml) still reads `run_state: SCAFFOLDING` although that run ended and wrote its completion report.

Counts are from `git ls-files notes/research` at the 2026-09-20 public tidy.

| Filename family | Count | What it is |
|---|---:|---|
| `*_STATE.yaml` | 18 | Sprint status, phase, gate flags and run ids, one per sprint. One sprint uses a combined Markdown file instead: [`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_STATE.md`](INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_STATE.md) |
| `*RESUME_NEXT_TASK.md` | 16 | The instruction the agent left for its next session |
| `*BACKLOG.md` | 15 | Queued work items per sprint |
| `*BLOCKERS.md` | 17 | What stopped progress, usually a missing data source or a decision reserved for the human owner |
| `*WORK_LOG.md` / `*OPERATIONS_LOG.md` | 7 + 3 | Terse running logs. A few contain real findings; the one that matters is [`RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md`](RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md) |
| `*collector_isolation*.md` | 16 | Per-sprint self-attestations that the scheduled 2026 collector (commit `dc73318`) and the paper-mode trading flags were untouched |
| `*current_truth*.md` (either case) | 10 | Start-of-sprint reconciliations of "what is true right now". Each is a snapshot, and later ones supersede earlier ones. [`PROGRAM_CURRENT_TRUTH.md`](PROGRAM_CURRENT_TRUTH.md)† (2026-06-21) is stale for the in-play line. [`v1_5_current_truth.md`](v1_5_current_truth.md) (2026-06-23) is a clearer mid-programme snapshot, but it predates the prospective benchmark and the later in-play lines |
| **Total** | **102** | of 325 files (295 Markdown, 19 YAML, 11 JSON), not counting this index |

**Why they are still here, flat, under their original names.** Scripts write reports, manifests and operations logs to fixed filenames in this directory, and at least one test reads a file here by path ([`tests/test_final_holdout.py`](../../tests/test_final_holdout.py) loads [`final_holdout_freeze_manifest.json`](final_holdout_freeze_manifest.json)). Moving or renaming files would break those paths and would blur the point-in-time record. The public tidy therefore only adds things: new files such as this index, and dated banners above superseded notes. It does not move, rename or delete anything in `notes/research/`.
