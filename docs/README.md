# Documentation index

This folder holds the lab's **protocols, policies, runbooks and design notes**. It is not where results are
reported. Two documents here do carry numbers: [`MODEL_CARD.md`](MODEL_CARD.md) summarises the evaluation of
the one approved model, and [`ERRATA.md`](ERRATA.md) gives corrected figures.

| You want | Go to |
|---|---|
| What the lab found, with sample sizes and caveats | the root [`README.md`](../README.md) |
| The research notes and completion reports behind each number | [`notes/research/`](../notes/research/) |
| Machine-readable decision ledgers, manifests and registries | [`data/reference/`](../data/reference/) |
| What was wrong, and how it was corrected | [`ERRATA.md`](ERRATA.md) |

Everything here is research-only and paper-only. Nothing in this repository is betting or financial advice.

## How to read the Status column

Every document below carries one of three labels. A few rows add a qualifier in brackets where only part
of a document is still current.

| Status | Meaning |
|---|---|
| **Current** | Describes the repository as it stands. Rules stated in these documents are still the rules. |
| **Historical** | Written for an earlier stage — mostly the original v0.1 toolkit, before any result existed. The reasoning can still be useful, but the document predates the findings and must not be read as what the lab concluded. |
| **Machine record** | A single-machine orchestration record: how a bounded research run was launched and supervised on the author's Windows PC. These runs need gitignored data or the author's external data lake, and some documents contain absolute local paths ([ERRATA E7](ERRATA.md#e7--stale-manifests-and-machine-specific-paths)). Read them as provenance, not as a portable recipe. |

**A naming trap.** Model labels collide across documents. `M1–M5` (pre-match shadow models), `M0–M6`
(in-play models) and the `M0–M14` ladder in the ablation plan are three unrelated schemes, and the same
remaining-time Poisson reference appears as M2, `m2_frozen`, W2, R2/R0, T0 and e2. "Tier" collides too:
Tier 1 / 2 / 4 are research phases, while Tier A–D are the lab's own sample-size labels for the prospective
benchmark. Keep [`GLOSSARY.md`](GLOSSARY.md) open while reading.

## Suggested reading paths

- **Ten minutes:** root [`README.md`](../README.md) → [`GLOSSARY.md`](GLOSSARY.md) → [`ERRATA.md`](ERRATA.md).
- **Judging the method:** [`AUTORESEARCH_GOVERNANCE.md`](AUTORESEARCH_GOVERNANCE.md) →
  [`BACKTEST_PROTOCOL_2018_2022_2026.md`](BACKTEST_PROTOCOL_2018_2022_2026.md) →
  [`INPLAY_EVALUATION_PROTOCOL.md`](INPLAY_EVALUATION_PROTOCOL.md) →
  [`PROSPECTIVE_SCORECARD_PROTOCOL.md`](PROSPECTIVE_SCORECARD_PROTOCOL.md) →
  [`SCORE_HARVEST_GUIDE.md`](SCORE_HARVEST_GUIDE.md).
- **Running the code:** [`../QUICKSTART.md`](../QUICKSTART.md) →
  [`TESTING_AND_DATA_DEPENDENCIES.md`](TESTING_AND_DATA_DEPENDENCIES.md) →
  [`DATA_SOURCES.md`](DATA_SOURCES.md).
- **How the AI agent was constrained:** [`ai-workflow/README.md`](ai-workflow/README.md).

---

## Start here

| Document | What it is | Status |
|---|---|---|
| [`../QUICKSTART.md`](../QUICKSTART.md) | Install, run the test suite, and operate the two scheduled processes (shadow collector and score harvester). The 2026 collection window has closed, so today it serves as a replay guide. | Current |
| [`GLOSSARY.md`](GLOSSARY.md) | Every model name and term in one place, including the colliding B / M / W / R / T / e labels and the lab's own Tier A–D sample-size labels. | Current |
| [`ERRATA.md`](ERRATA.md) | Known defects and corrections E1–E7, including two latent bugs found only during the 2026-09-20 release review. | Current |
| [`MODEL_CARD.md`](MODEL_CARD.md) | Model card for B1 ternary Elo, the only approved model: details, intended and out-of-scope uses, evaluation data, results with their intervals, known limitations and errata. Replaced the v0.1 design-time card on 2026-09-20. | Current |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | Every third-party data source, its licence or terms, the attribution it requires, what this repository does and does not redistribute, and how to obtain the data yourself. The MIT licence covers the code only. | Current |

## Concepts & statistics

Apart from the toolkit how-to, these were written with the original v0.1 command-line toolkit. The CLI they
describe still exists (`src/wcdrawlab/cli.py`, twelve subcommands), but they predate every result in the
root README.

| Document | What it is | Status |
|---|---|---|
| [`TOOLKIT_USAGE.md`](TOOLKIT_USAGE.md) | The v0.1 toolkit how-to, formerly the root README, with stale details corrected on 2026-09-20: install, synthetic demo, public-data fetch, truth tables, backtest, risk columns, after-game updates and a reference for all twelve CLI subcommands. It records one known defect: `predict-live` writes its output files and then exits with an error. It is not the results page and not the prospective-pipeline guide. | Current |
| [`PROBABILITY_AND_STATISTICAL_REASONING.md`](PROBABILITY_AND_STATISTICAL_REASONING.md) | The maths: the three-way probability vector, scoreline (Poisson / Dixon-Coles) reasoning, rating gaps, tournament state, the market as a benchmark, and the proper scoring rules. The scoring-rule definitions in §9 (log loss, RPS, draw Brier, draw calibration error) are the ones still used. Its case for a scoreline backbone was not borne out: the scoreline models showed no evidence of improvement over plain Elo on the 144 pooled development-fold matches. | Historical |
| [`MODEL_ARCHITECTURE.md`](MODEL_ARCHITECTURE.md) | The seven-layer design (time-safe data, strength, scoreline, draw calibration, tournament-state simulator, context modules, market residual). Only the strength layer — B1 ternary Elo — became the approved runtime model. The scoreline and draw-recalibration layers showed no evidence of improvement at the available sample size, context features were specified but never fitted, and the market layer could not be tested on the development folds because pre-2020 odds do not exist. | Historical |
| [`RISK_AND_UNCERTAINTY.md`](RISK_AND_UNCERTAINTY.md) | How the per-prediction uncertainty columns are computed in `src/wcdrawlab/risk.py`: outcome standard deviation, a Beta interval from an effective sample size, entropy, a confidence score and a risk band. The intervals are approximations, not a Bayesian posterior. | Historical |
| [`ELO_UPDATE_SYSTEM.md`](ELO_UPDATE_SYSTEM.md) | The internal Elo table: update formula, why ratings are kept in-house rather than fetched, and the `update-elo` commands. | Historical |
| [`PREDICTION_TARGETS_AND_UPDATE_CADENCE.md`](PREDICTION_TARGETS_AND_UPDATE_CADENCE.md) | What the toolkit outputs per match (1X2 probabilities, advancement and third-place probabilities, draw utility, risk columns) and when each input should be refreshed. | Historical |
| [`AFTER_GAME_UPDATE_WORKFLOW.md`](AFTER_GAME_UPDATE_WORKFLOW.md) | Step-by-step CLI workflow for entering a final score and recomputing the remaining forecasts. Two cautions: its first step copies a seed file over `data/live/current_matches.csv`, which is a tracked file, so work on a copy; and its next command, `predict-live`, has the known defect described in [`TOOLKIT_USAGE.md`](TOOLKIT_USAGE.md). | Historical |

## Evaluation protocols

| Document | What it is | Status |
|---|---|---|
| [`BACKTEST_PROTOCOL_2018_2022_2026.md`](BACKTEST_PROTOCOL_2018_2022_2026.md) | The original time-ordered fold design (2018, 2022, locked 2026 Matchday 1) and the event-driven replay rules. `configs/research.yaml` still encodes these folds for the fixed evaluator. One later refinement: after an internal audit found that the 2022 fold had been used during model selection, selection moved to development folds 2010 / 2014 / 2018 (`configs/research_dev.yaml`) and 2022 became a read-once release gate. | Current |
| [`INPLAY_EVALUATION_PROTOCOL.md`](INPLAY_EVALUATION_PROTOCOL.md) | In-play split and significance rules: never split rows at random, leave-one-group-out folds, match-level paired bootstrap, train-fold-only calibration, fixed reporting breakdowns. Written for the 48-match 2022 foundation, and says itself why one tournament is not enough; later research lines extend it to leave-one-competition-out and nested evaluation. | Current |
| [`PROSPECTIVE_SCORECARD_PROTOCOL.md`](PROSPECTIVE_SCORECARD_PROTOCOL.md) | Deterministic scoring rules for the frozen pre-match shadow models: one primary snapshot per match, the fixture as the unit of analysis, canonical model IDs, metrics, sample-size tiers, and no selection or recalibration. Two parts are dated. Its "Current status" paragraph was written when the prospective pool still had 0 finalized eligible matches, and its tier list stops at C (tier D, 50 or more fixtures, is defined in the [glossary](GLOSSARY.md)). The 34-fixture outcome, a null result against an early market line, is in [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](../notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md); see the caveat under [Prospective 2026 operations](#prospective-2026-operations). | Current (rules); Historical (status paragraph) |
| [`ABLATION_AND_TESTING_PLAN.md`](ABLATION_AND_TESTING_PLAN.md) | The design-time test plan: a planned `M0–M14` ablation ladder, primary metrics, pass/fail thresholds and nine hypotheses. Its `M` labels are unrelated to the shadow or in-play model names. Its betting diagnostics were never computed; every result in this repository is a forecast-quality metric. | Historical |

## Data contracts, leakage & source governance

| Document | What it is | Status |
|---|---|---|
| [`DATA_CONTRACTS_AND_LEAKAGE.md`](DATA_CONTRACTS_AND_LEAKAGE.md) | The base rule — no feature may postdate kickoff — plus the input schemas (matches, ratings, odds), as-of joins and the seed-data warning. | Current |
| [`LIVE_DATA_CONTRACTS.md`](LIVE_DATA_CONTRACTS.md) | Prose companion to `schemas/live_data_contracts.yaml`: the append-only raw provenance envelope, the decision-time rule and normalized schemas A–Q. It states itself that no live feed flows through these contracts yet. | Current |
| [`EVENT_RECONCILIATION_POLICY.md`](EVENT_RECONCILIATION_POLICY.md) | How events from several providers are matched without ever silently merging a conflict: source priority, matching rules and verdicts. Implemented in `wcdrawlab.ingestion.reconcile` and covered by tests. | Current |
| [`CONTEXT_FEATURE_AVAILABILITY_POLICY.md`](CONTEXT_FEATURE_AVAILABILITY_POLICY.md) | Availability rules for venue, travel, rest, timezone and weather features (forecast weather only; observed weather is retrospective). A contract plus helpers; no model was fitted on these features. | Current |
| [`DATA_SOURCE_GOVERNANCE.md`](DATA_SOURCE_GOVERNANCE.md) | Read-only provider adapters, the request-before-implementation rule for any new source ([`data_requests/`](../data_requests/)), the restrictive scraping allowlist and the data-quality hierarchy. | Current |
| [`LICENSED_EVENT_PROVIDER_ACCEPTANCE_PROTOCOL.md`](LICENSED_EVENT_PROVIDER_ACCEPTANCE_PROTOCOL.md) | Six gating categories a paid event-data vendor must pass before its data may be stored or trained on; any unknown right fails. No vendor was contacted and nothing was purchased. | Current |
| [`ACCOUNT_AND_API_SETUP.md`](ACCOUNT_AND_API_SETUP.md) | Which provider accounts and environment variables the pipelines expect, and when each is needed. Keys live only in a local `.env`. No Kalshi credentials were ever configured, so the "create later" section was never acted on in this repository. | Current |

## Prospective 2026 operations

Two separate collectors exist, and they are easy to confuse.

- The **pre-match shadow collector** froze the pre-match shadow models M1–M5 before kickoff: `M1_B1` is B1,
  `M2_market` is the no-vig bookmaker consensus (a read-only comparator), and M3–M5 are fixed B1/market
  blends whose weights were never tuned. Its frozen predictions are what the 34-fixture benchmark scored.
- The **V1.5 collector** was built for the frozen in-play research model `m2_frozen` (the in-play M2, a
  different namespace from `M2_market`). No in-play prediction from it was ever scored, so its documents
  describe machinery, not a result.

Only the group stage was collected. Knockout rounds were never collected or scored.

> [!IMPORTANT]
> **Read the 34-fixture benchmark with two caveats.** It is a null result: none of the reported paired
> differences has a 95% interval that excludes zero, so there is no evidence at this sample size that B1,
> the market or any fixed blend differs from the others. And the market comparator is an **early line, not a
> closing line**: for 31 of 34 fixtures the snapshot used is from 2026-06-21, a median of about 98 hours
> before kickoff ([ERRATA E2](ERRATA.md#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger)).
> The snapshot-selection rule was pre-specified and outcome-independent, but that ordering is
> self-attested: the rule, the script and the results share one commit.

| Document | What it is | Status |
|---|---|---|
| [`SCORE_HARVEST_GUIDE.md`](SCORE_HARVEST_GUIDE.md) | Operations guide for the independent, idempotent, append-only score harvester: why it exists (the collector's own scoring step silently scored nothing), what each script does, its guarantees, and how to read the benchmark files. This is the only working scoring path ([ERRATA E3](ERRATA.md#e3--the-collectors-own-scoring-step-was-never-repaired)). | Current |
| [`DURABLE_COLLECTOR_AND_SCHEDULER.md`](DURABLE_COLLECTOR_AND_SCHEDULER.md) | The first collection design (a bounded five-hour supervisor with hard credit caps) and the six-point bar a research model must clear to be labelled a shadow candidate. It records that no model cleared it. The scheduled single-cycle collector described in QUICKSTART later became the operating path. | Historical |
| [`PROSPECTIVE_COLLECTION_RUNBOOK.md`](PROSPECTIVE_COLLECTION_RUNBOOK.md) | Operating the V1.5 collector for `m2_frozen`: capture windows, dry-run by default, first-write-wins ledger, integrity check, resume after restart. | Current (machinery only) |
| [`PROSPECTIVE_DATA_DICTIONARY.md`](PROSPECTIVE_DATA_DICTIONARY.md) | Field-by-field dictionary for the V1.5 prediction ledger and score records. | Current |
| [`PROSPECTIVE_OPERATIONS_CHECKLIST.md`](PROSPECTIVE_OPERATIONS_CHECKLIST.md) | Pre-activation, activation and in-tournament checklist for the V1.5 collector. Activation steps are written as the owner's decision. | Historical |
| [`WINDOWS_SCHEDULER_SETUP.md`](WINDOWS_SCHEDULER_SETUP.md) | Windows Task Scheduler setup for the V1.5 collector: bounded single-pass runs, dry-run until `EXECUTE=1`. Written for the author's machine. | Machine record |
| [`CRON_SETUP.md`](CRON_SETUP.md) | The cron equivalent for Linux / macOS / WSL. The lab's own runs used Windows Task Scheduler. | Current |

## Research-line runbooks

Each runbook documents one bounded, restart-safe job queue — or, in one case, its watchdog — driven by the
same controller (`scripts/deep_research_supervisor.py`). All are **machine records**.

For what each line found, read the linked completion report. Most lines ended with no evidence, at the
available sample size, that any model improves on its reference. Those outcomes are reported as plainly as
the few positive ones.

| Document | What it is | Outcome, and where to read it | Status |
|---|---|---|---|
| [`DEEP_RESEARCH_CONTROLLER_RUNBOOK.md`](DEEP_RESEARCH_CONTROLLER_RUNBOOK.md) | The controller itself: a finite ordered job queue with a hard deadline, an API budget and a stop on a stale collector heartbeat. | Reused by every later line. [Completion report](../notes/research/DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION.md). | Machine record |
| [`RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_RUNBOOK.md`](RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_RUNBOOK.md) | 16-job run to reconcile conflicting counts, complete the API-Football corpus and join xG to snapshots. Its status block is an early point-in-time snapshot. | The sprint was closed as incomplete and tagged `research-truth-full-corpus-xg-fusion-incomplete`. [Completion report](../notes/research/RESEARCH_TRUTH_FULL_CORPUS_XG_FUSION_COMPLETION.md). | Machine record |
| [`RESEARCH_TRUTH_FUSION_WATCHDOG_RUNBOOK.md`](RESEARCH_TRUTH_FUSION_WATCHDOG_RUNBOOK.md) | The 15-minute watchdog for that run: its state machine, what it may read and write, and the rule that it never restarts after an integrity failure. | [Operations log](../notes/research/RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md), including the internal audit that caught over-reported corpus coverage. | Machine record |
| [`DYNAMIC_INPLAY_MODELING_PHASE_RUNBOOK.md`](DYNAMIC_INPLAY_MODELING_PHASE_RUNBOOK.md) | 16-job offline evaluation of dynamic in-play model families on pre-2026 internationals. | 0 candidates promoted; a mis-scoring that had flagged a baseline as a candidate was caught and corrected. [Completion report](../notes/research/DYNAMIC_INPLAY_MODELING_PHASE_V1_COMPLETION.md). | Machine record |
| [`EVENT_PROCESS_INTELLIGENCE_RUNBOOK.md`](EVENT_PROCESS_INTELLIGENCE_RUNBOOK.md) | A two-line stub for the 16-job event-process run on StatsBomb Open Data. | On the 58-match cohort every e3–e9 model was worse than the reference e2; 0 candidates. [Completion report](../notes/research/EVENT_PROCESS_INTELLIGENCE_V1_COMPLETION.md). | Machine record |
| [`RESIDUAL_GOAL_INTENSITY_V1_RUNBOOK.md`](RESIDUAL_GOAL_INTENSITY_V1_RUNBOOK.md) | Run testing whether an event-process correction improves on the remaining-time Poisson reference intensity. | The reference stayed best; 0 candidates. [Completion report](../notes/research/RESIDUAL_GOAL_INTENSITY_V1_COMPLETION.md). | Machine record |
| [`EVIDENCE_POWER_CONSOLIDATION_V1_RUNBOOK.md`](EVIDENCE_POWER_CONSOLIDATION_V1_RUNBOOK.md) | 12-job, local-artifact-only run that consolidates the evidence and computes match-level statistical power. | Match-level power analysis on the 58-match cohort: adding more snapshots per match (1× to 8×) left power flat, because the match, not the snapshot, is the independent unit. The power figures in this report rest on an optimistic noise template and are superseded by the [231-match analysis](../data/reference/international_event_lake_power_analysis.md): power 0.28 for a 0.005 absolute RPS gain, with 0.80 first reached at the 1,200-match grid point. [Completion report](../notes/research/EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md). | Machine record |
| [`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_RUNBOOK.md`](INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_RUNBOOK.md) | 13-job run that restores and hash-verifies a content-addressed StatsBomb Open Data store for men's internationals, then reruns the pre-specified model families. The lake sits on the author's disk and is not redistributed. | No model cleared the locked multi-rule gate on the 231 model-eligible matches; the report and the ledger use two vocabularies for that outcome ([ERRATA E6](ERRATA.md#e6--two-vocabularies-for-the-same-event-lake-outcome)). [Completion report](../notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md). | Machine record |
| [`HIERARCHICAL_DOMAIN_TRANSFER_V1_RUNBOOK.md`](HIERARCHICAL_DOMAIN_TRANSFER_V1_RUNBOOK.md) | 14-job run for a club-to-international transfer ladder judged against the T0 reference. | Incomplete and null: no model beat T0, the run had 0 club training rows so cross-domain lift is untested, and the decision ledger the runbook cites is missing ([ERRATA E5](ERRATA.md#e5--the-hierarchical-transfer-decision-ledger-is-missing)). [Completion report](../notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md). | Machine record |

Several runbooks call the remaining-time Poisson reference "parameter-free". The accurate description is
*unfitted, with hand-set constants* (base goal rate 1.35, Elo coefficient 0.20). See the
[glossary](GLOSSARY.md).

## Commentary policies

The commentary side line works on European **club** football broadcasts, not the World Cup. The repository
tracks no commentary text and no SoccerNet label files — only manifests and aggregates. No outcome model
was trained on commentary.

| Document | What it is | Status |
|---|---|---|
| [`COMMENTARY_DATA_LICENSING_POLICY.md`](COMMENTARY_DATA_LICENSING_POLICY.md) | Per-source rights rules: every use is denied until an official term permits it, no scraping under uncertain terms, no raw copyrighted text in git, synthetic text only in tests. | Current |
| [`COMMENTARY_CAUSALITY_POLICY.md`](COMMENTARY_CAUSALITY_POLICY.md) | Separates event time, commentary clock time and publication time. A line without a known publication time may be used for historical labelling only, never as a live input. | Current |
| [`COMMENTARY_LIVE_ELIGIBILITY_GATE.md`](COMMENTARY_LIVE_ELIGIBILITY_GATE.md) | The ten conditions a commentary source must meet to count as live-eligible, with a validator that exits non-zero on a violation. Current result: no source is live-eligible. | Current |

## Testing

| Document | What it is | Status |
|---|---|---|
| [`TESTING_AND_DATA_DEPENDENCIES.md`](TESTING_AND_DATA_DEPENDENCIES.md) | The two test tiers: synthetic unit tests that must pass on a fresh clone, and integration tests that need gitignored data and are skipped with an explicit reason (`pytest -rs` shows why). The document quotes no count. The release check on 2026-09-20 (fresh-clone conditions, Python 3.13, Windows) gave 817 passed, 51 skipped, 0 failed; the 51 skips are the integration tests. | Current |

## Dormant trading scaffold

`src/wcdrawlab/trading/` is a dormant, triple-gated paper/demo execution scaffold: never armed, never
given credentials ("Kalshi: credentials MISSING"), and no order was ever placed. The production order path
raises unless `require_live` **and** `KALSHI_ENABLE_LIVE_TRADING=true` **and** an exact acknowledgement
string are all present. The collector hard-halts (exit 3) unless `KALSHI_ENABLE_LIVE_TRADING=false` and
`TRADING_MODE=paper`. All results in this repository are forecast-quality metrics, never P&L.

One nuance: the risk gate's approved-model check applies only when a trade intent carries a `model_id`,
which is an optional field. "Fail-closed" is therefore accurate for the *forecaster* path, not for the
whole trading path. The module is kept and labelled rather than hidden or deleted.

Two CLI subcommands, `trade-check` and `trade-submit`, sit in front of this scaffold. They are documented
in [`TOOLKIT_USAGE.md`](TOOLKIT_USAGE.md). Nothing here is betting or financial advice.

| Document | What it is | Status |
|---|---|---|
| [`LIVE_TRADING_ARCHITECTURE.md`](LIVE_TRADING_ARCHITECTURE.md) | Design of the separation between data, prediction, decision, risk gate and the paper / demo / live gateway, including the order gate and kill switches. A governance-protected file. It describes a scaffold that was never armed. | Historical |
| [`BETTING_RISK_POLICY.md`](BETTING_RISK_POLICY.md) | Why a probability forecast is not a bet: fair odds, expected value and variance per unit, Kelly sizing, and practices to reject. Design-time material; nothing in this repository was ever bet, and none of these quantities was ever reported as a result. | Historical |

## AI-assisted workflow

The lab was directed by a human and executed by an AI coding and research agent (Claude Code) under a
written contract. The reviews described in the notes are internal agent audits, not third-party reviews.

| Document | What it is | Status |
|---|---|---|
| [`ai-workflow/README.md`](ai-workflow/README.md) | How the lab was built: the fixed evaluator, the single editable file, protected paths, data-request gating, decision ledgers, what the internal audits caught, who decided what, and the limits of the arrangement. | Current |
| [`AUTORESEARCH_GOVERNANCE.md`](AUTORESEARCH_GOVERNANCE.md) | Why the research plane and the execution plane share no authority, the frozen protocol, the composite objective and the promotion steps. A governance-protected file. Read with the contract in [`../program.md`](../program.md). | Current |
| [`ai-workflow/START_HERE_CLAUDE_CODE.md`](ai-workflow/START_HERE_CLAUDE_CODE.md) | The six-step handoff checklist used to open a Claude Code session on this repository. | Current |
| [`ai-workflow/CLAUDE_CODE_MASTER_PROMPT.md`](ai-workflow/CLAUDE_CODE_MASTER_PROMPT.md) | The current first prompt: reading order, the SET / MISSING configuration audit, the fold hierarchy, baselines B0–B7, the autoresearch loop and the data-request rule. | Current |
| [`ai-workflow/CLAUDE_CODE_BOOTSTRAP_PROMPT.md`](ai-workflow/CLAUDE_CODE_BOOTSTRAP_PROMPT.md) | The older, shorter first prompt, superseded by the master prompt. | Historical |

## History

| Document | What it is | Status |
|---|---|---|
| [`history/VERSION.md`](history/VERSION.md) | The Tier-1 version manifest of 2026-06-20, kept unedited under a SUPERSEDED banner that lists what it gets wrong today. Do not cite it. | Historical |
| [`history/BUILD_VALIDATION.md`](history/BUILD_VALIDATION.md) | Validation record of the original v0.1 package, kept under a historical banner. Its test count is stale; do not cite it. | Historical |

The dated milestone log is the root [`CHANGELOG.md`](../CHANGELOG.md).

## Figures

| Path | What it is | Status |
|---|---|---|
| [`img/README.md`](img/README.md) | What each figure shows, the source file of every plotted number, the caveats printed on the figures, and how to regenerate both with the dependency-free script `scripts/make_readme_figures.py`. | Current |
| [`img/prospective_paired_deltas.svg`](img/prospective_paired_deltas.svg) | Forest plot of the paired RPS differences on the 34 prospective fixtures. Every 95% interval includes zero, and the market shown is an early line, not a closing line. | Current |
| [`img/power_curve.svg`](img/power_curve.svg) | Match-clustered power against number of matches for several RPS gains. With the 231 matches available, power for a 0.005 absolute RPS gain is 0.28. The lines only join the values stored in the committed power-analysis file; they are not fitted curves. | Current |
