# Glossary

Plain-English definitions for the model names, metrics, evaluation terms and status labels used
across this repository. Each entry says where the term is defined, so you can check it yourself.

Two conventions hold everywhere:

- **Lower is better** for every metric listed here (RPS, log-loss, Brier, calibration error, composite).
- A **paired delta** such as `dRPS` is *candidate minus reference*. Negative means the candidate
  scored better. A delta only counts as a difference when its 95% confidence interval excludes zero.

## Read this first: three naming traps

Short labels were reused across research lines. A bare label is ambiguous without its context.

| Trap | What collides | How to tell them apart |
|---|---|---|
| `M1`-`M5` | Pre-match shadow models (`M2` = bookmaker consensus) **vs** in-play ladder `M0`-`M6` (`M2` = remaining-time Poisson) | Resolve by namespace (`prematch.*` / `inplay.*`) through [`configs/model_alias_registry.yaml`](../configs/model_alias_registry.yaml) |
| `R0`/`R1`/`R2` and `h0`-`h4` | Dynamic in-play phase (`R2` = Poisson reference, `R0` = static anchor) **vs** residual goal-intensity phase (`R0`, written `r0` in ids, = the Poisson reference; `h*` = `research.horizon.*`) **vs** event-process phase (`h*` = `research.scoring.*`, a different near-term target) | Use the full dotted id, for example `research.wdl.remaining_time_poisson_r2` or `research.residual.w2_reference_r0` |
| "Tier" | **Tier 1 / 2 / 4** are research phases (data layer, baseline gate, in-play sprint). **Tier A-D** are sample-size labels for the prospective benchmark | Numbers = phase, letters = sample size |

The collision and its fix are written up in
[`notes/research/model_namespace_reconciliation.md`](../notes/research/model_namespace_reconciliation.md).
Historical prediction rows were never rewritten; legacy labels are resolved at read time.

---

## 1. Pre-match models

Pre-match models output three probabilities for a fixture before kickoff: team A win, draw, team B
win (also written 1X2).

### Baseline suite B0-B7

Defined in [`scripts/tier2_baselines.py`](../scripts/tier2_baselines.py); results in
[`notes/research/tier_2_baseline_gate.md`](../notes/research/tier_2_baseline_gate.md).

| ID | What it is | Defined in |
|---|---|---|
| **B0** | Frequency prior: historical win/draw/loss rates, identical for every match. | `HistoricalPriorModel` in [`src/wcdrawlab/models/baselines.py`](../src/wcdrawlab/models/baselines.py) |
| **B1** (`B1_ELO`, `M1_B1`, `prematch.b1_elo`) | Ternary Elo. Takes the Elo expected score `p` and sets `P(A) = p^2 + r*p*(1-p)`, `P(B) = (1-p)^2 + r*p*(1-p)`, draw = the remainder, with `r = 0.4` hand-set. No fitted parameters: `r` and the Elo rating constants are hand-set, not estimated. **The only runtime-approved model.** Approved because nothing improved on it with significance, not because it is strong; see the [model card](MODEL_CARD.md). | `ternary_elo_probs` in [`src/wcdrawlab/ratings.py`](../src/wcdrawlab/ratings.py); registry entry in [`configs/approved_models.yaml`](../configs/approved_models.yaml) |
| **B2** | FIFA-ranking-only multinomial logit. | `b2` in `scripts/tier2_baselines.py` |
| **B3** | Elo plus host-advantage multinomial logit. | `b3` in `scripts/tier2_baselines.py` |
| **B4** | Independent Poisson scoreline model (also gives expected goals). | [`src/wcdrawlab/models/scoreline.py`](../src/wcdrawlab/models/scoreline.py) |
| **B5** | B4 with a fixed Dixon-Coles-style low-score correction (rho = -0.05, diagonal inflation 0.05). | `b5` in `scripts/tier2_baselines.py` |
| **B6** | No-vig bookmaker consensus. Available for the **2022 fold only**, because timestamped odds do not exist for earlier folds. | `market_probs_2022` in `scripts/tier2_baselines.py` |
| **B7** | Calibrated ensemble of B1, B5 and a general logit, with draw recalibration fitted on training data only. Has a no-market variant (all folds) and a market variant (2022 only). | `b7_nomarket` in `scripts/tier2_baselines.py` |

### Candidate and blends

| ID | What it is | Status | Defined in |
|---|---|---|---|
| **V8** (`V8_ELO_BLEND_LOGIT`) | The autoresearch candidate: a standardized multinomial logit blended with ternary Elo at weight 0.85 on Elo. | Shadow-only, never approved. See [erratum E1](ERRATA.md#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug) before quoting any V8 number. | [`src/wcdrawlab/research/candidate.py`](../src/wcdrawlab/research/candidate.py) |
| `MARKET_ELO_BLEND` | 0.6 x no-vig market + 0.4 x ternary Elo; an early forecast aid. | Shadow-only. No cross-fold backtest is possible (no pre-2020 odds). | [`scripts/market_anchored_forecast.py`](../scripts/market_anchored_forecast.py) |

### Pre-match shadow models M1-M5 (2026 prospective study)

Canonical ids are in [`schemas/model_identity_v1.yaml`](../schemas/model_identity_v1.yaml). The blend
weights were fixed in advance and never tuned.

| Label | Canonical id | What it is |
|---|---|---|
| `M1_B1` | `prematch.b1_elo` | B1 itself. |
| `M2_market` | `prematch.market_novig` | No-vig bookmaker consensus. A read-only comparator, never a candidate. In the 2026 benchmark (34 scored fixtures) it is mostly an **early line**, not a closing line; see [Early line vs closing line](#6-operations-terms-2026-prospective-collection). |
| `M3_75_25` | `prematch.elo_market_blend_75_25` | 75% B1 / 25% market. |
| `M4_50_50` | `prematch.elo_market_blend_50_50` | 50% B1 / 50% market. |
| `M5_25_75` | `prematch.elo_market_blend_25_75` | 25% B1 / 75% market. |

The snapshot-selection note writes the blend ids in a shorter form (`prematch.blend_75_25` and so
on). The registry ids above are the canonical ones.

---

## 2. In-play models

In-play models update win/draw/loss probabilities during a match from the clock, the score and
(sometimes) other match state. **All in-play models are research-only.** None was approved, and
none was ever scored prospectively.

### In-play ladder M0-M6

Defined in [`src/wcdrawlab/research/inplay_models/models.py`](../src/wcdrawlab/research/inplay_models/models.py).

| Label | What it is | Fitted? |
|---|---|---|
| **M0** (`M0_static_b1`) | The pre-match B1 forecast held constant for the whole match. The control. | No |
| **M1** (`M1_time_score`) | Logistic model on score difference, remaining minutes, Elo gap and red-card difference. | Yes |
| **M2** (`M2_remaining_poisson`) | Remaining-time Poisson. Pre-match goal rates come from a hand-set mapping (base rate 1.35, Elo coefficient 0.20), then an in-play engine conditions on minute, score and red cards. **Unfitted, with hand-set constants.** | No |
| **M3** (`M3_goal_hazard`) | Probability of any goal in the next 5 minutes. Listed as `rejected` in the identity registry. | Yes |
| **M4** (`M4_competing_risk`) | Which team scores next (home / away / none). Listed as `rejected`. | Yes |
| **M5** (`M5_ensemble`) | Average of M1 and M2 with a recalibration fitted on training folds. | Yes |
| **M6** (`M6_market_inplay`) | M2's dynamics, but the pre-match strength gap comes from market odds instead of Elo (it falls back to Elo when no market price is present). | No |
| `M2cal`, `M2fit`, `M2temp`, `M2fit_temp` | Recalibrated, goal-rate-fitted and temperature-scaled variants of M2. `M2fit_temp` was once called "best" after repeated looks at 2026 results; that claim is now labelled `invalid_due_to_model_selection_on_test_set`. | Yes |

### One reference model, seven labels

The remaining-time Poisson reference is the benchmark that every later in-play candidate had to
improve on. It appears under seven labels (M2, `m2_frozen`, W2, R2, e2, R0 and T0). Reading the
code shows **two variants** of the same idea:

| Label | Research line | Uses Elo? | Defined in |
|---|---|---|---|
| **M2** / `M2_remaining_poisson` | In-play ladder | Yes (base 1.35, Elo coefficient 0.20, red-card aware engine) | [`inplay_models/models.py`](../src/wcdrawlab/research/inplay_models/models.py) |
| **`m2_frozen`** | Frozen prospective in-play protocol (v2 freeze) | Yes (same constants, temperature 1.0) | [`final_holdout.py`](../src/wcdrawlab/research/final_holdout.py), [`final_holdout_freeze_manifest_v2.json`](../notes/research/final_holdout_freeze_manifest_v2.json) |
| **W2** | Deep-research in-play foundation (627 API-Football internationals) | No. Both teams share 1.35 goals per 90 minutes, scaled by time remaining, combined with the current score difference | [`scripts/research_jobs/_models.py`](../scripts/research_jobs/_models.py) |
| **R2** (`research.wdl.remaining_time_poisson_r2`) | Dynamic in-play phase | No (same closed form as W2) | [`dynamic_models.py`](../src/wcdrawlab/research/dynamic_models.py) |
| **e2** (`research.event_process.e2`) | Event-process intelligence, event-lake rerun | No | [`event_process/models.py`](../src/wcdrawlab/research/event_process/models.py) |
| **R0** (`research.residual.w2_reference_r0`) and **T0** (`research.transfer.w2_reference_t0`) | Residual goal intensity; hierarchical transfer | No | [`residual_intensity/models.py`](../src/wcdrawlab/research/residual_intensity/models.py), [`transfer/w2_reference_t0.py`](../src/wcdrawlab/research/transfer/w2_reference_t0.py) |

The code comments say the later references are "reimplemented, NOT the frozen prospective M2". So
treat these as one model *specification* with an Elo-aware original and a symmetric re-implementation.
Do not compare RPS values across research lines: the datasets, snapshot grids and variants differ.

Code comments and the v2 freeze manifest describe this reference as having no free parameters. Read
that as **unfitted**: the constants (1.35, and 0.20 in the Elo-aware variant) are hand-set, not
estimated. `m2_frozen` was frozen but never scored; the freeze is governance machinery, not a result.

### Research model families

All of these carry five labels: `research_only`, `experimental`, `not_runtime_approved`,
`not_trade_eligible` and `not_live_eligible`. No family produced a promoted model.

| Family | Research line | Members | Defined in | Verdicts recorded in |
|---|---|---|---|---|
| **W0-W4** | Deep-research in-play foundation | W0 base rate, W1 score-difference empirical, W2 Poisson reference, W3 team-state logistic, W4 plus lineup continuity. Companions: `N0`-`N2` (next goal), `C0`-`C1` (cards). | [`scripts/research_jobs/_models.py`](../scripts/research_jobs/_models.py) | [`DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION.md`](../notes/research/DEEP_RESEARCH_INPLAY_FOUNDATION_COMPLETION.md) |
| **R0-R2** (dynamic) | Dynamic in-play phase | References only: R0 static anchor, R1 time + score, R2 Poisson. | [`dynamic_models.py`](../src/wcdrawlab/research/dynamic_models.py) | [`data/reference/model_decision_ledger.csv`](../data/reference/model_decision_ledger.csv) |
| **P1-P5** | Dynamic in-play phase | Player-prior candidates: starting XI, on-pitch, substitution delta, composition, full team state. All `rejected`. | `dynamic_models.py` | `model_decision_ledger.csv` |
| **X1-X3** | Dynamic in-play phase | xG candidates scored on a smaller xG-matched subset: event state, player state, calibrated hybrid. X1 and X3 `rejected`, X2 `reference_only`. | `dynamic_models.py` | `model_decision_ledger.csv` |
| **e0-e9** | Event-process intelligence | e0 base rate, e1 time + score, **e2 Poisson reference**, e3 xG, e4 possession + territory, e5 transition + pressure, e6 set piece + discipline, e7 full state, e8 e7 plus a club-trained representation, e9 calibrated hybrid. All `reference_only`. On the 231-match rerun e9 had a lower LOCO RPS than e2 but failed the locked log-loss and forward-chain rules, so it is **not** a positive result (erratum E6). | [`event_process/models.py`](../src/wcdrawlab/research/event_process/models.py) | [`event_process_model_decision_ledger.csv`](../data/reference/event_process_model_decision_ledger.csv), [`international_event_lake_model_decision_ledger.csv`](../data/reference/international_event_lake_model_decision_ledger.csv) |
| **q0-q4** | Event-process intelligence | Next-goal hazard: a goal by either side in the next 15 minutes. q0 is the base-rate reference. | `event_process/models.py` | `event_process_model_decision_ledger.csv` |
| **h0-h3** (event-process) | Event-process intelligence | Near-term scoring: any goal in the next 10 minutes. h0 is the base-rate reference. | `event_process/models.py` | `event_process_model_decision_ledger.csv` |
| **y0-y2** | Event-process intelligence | Sending-off hazard. y1 and y2 were gated off (`data_insufficient`, fewer than 150 positives). | `event_process/models.py` | `event_process_model_decision_ledger.csv` |
| **r0-r6**, **i0-i3**, **h0-h4** (residual) | Residual goal intensity | Corrections expressed relative to the Poisson reference: W/D/L (`r*`), home/away intensity (`i*`), near-term horizon (`h*`). The `*0` member is always the reference. | [`residual_intensity/models.py`](../src/wcdrawlab/research/residual_intensity/models.py) | [`residual_goal_intensity_decision_ledger.csv`](../data/reference/residual_goal_intensity_decision_ledger.csv) |
| **T0-T7** | Hierarchical club-to-international transfer | T0 Poisson reference, T1 international-only, T2 naive club pooling (diagnostic only), T3 shared stable features, T4 partial pooling, T5 domain-weighted, T6 selective transfer, T7 calibrated simulation. The run had no club training rows, so transfer is **untested**; its decision ledger is missing (erratum E5). | [`hierarchical_transfer/`](../src/wcdrawlab/research/hierarchical_transfer/__init__.py) | [`HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md`](../notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md) |

`P1`-`P4` also appear in an earlier player-impact sprint, where a job script mapped them onto the
inherited W1-W4 predictors. That sprint's table was identical to the previous sprint's and was later
downgraded to incomplete. Only the dynamic-phase P1-P5 are distinct models.

---

## 3. Metrics

Core implementations: [`src/wcdrawlab/evaluation.py`](../src/wcdrawlab/evaluation.py) and
[`src/wcdrawlab/research/runner.py`](../src/wcdrawlab/research/runner.py).

| Metric | Meaning | Defined in |
|---|---|---|
| **RPS** (ranked probability score) | Squared error between cumulative forecast and cumulative outcome over the ordered classes (A win, draw, B win), divided by 2. Rewards putting probability *near* the right outcome, which suits an ordered result. | `rps_3way` in `evaluation.py` |
| **Log-loss** (three-way) | Negative log of the probability given to the actual outcome. Punishes confident misses heavily. | `log_loss_3way` in `evaluation.py` |
| **Brier score** | Mean squared error of a probability against a 0/1 outcome. | `brier_draw` in `evaluation.py` |
| **Draw-Brier** | Brier score of the draw probability against "was it a draw?". | `brier_draw` in `evaluation.py` |
| **Draw calibration error** | Binned gap between predicted draw probability and observed draw rate, weighted by bin size (8 bins). This is the fourth term of the composite. Also written "draw-cal". | `draw_calibration_error` in `runner.py` |
| **ECE** (expected calibration error) | Binned gap between confidence and accuracy. **Two versions exist.** The prospective scorecard uses a 10-bin *top-label* ECE (confidence = the largest of the three probabilities). Pre-match code also has a 10-bin *draw* ECE. With 34 fixtures either is descriptive only. | `_ece` in [`scripts/prospective_score_harvester_v1.py`](../scripts/prospective_score_harvester_v1.py); `expected_calibration_error_draw` in `evaluation.py` |
| **Calibration slope / intercept** | Fit a logistic regression of "was it a draw?" on the logit of the predicted draw probability. Slope 1 and intercept 0 are ideal; slope below 1 means overconfident. Very noisy with about 10 draws per fold. | `_cal_slope_intercept` in the harvester; `calibration_slope_intercept` in [`inplay_eval.py`](../src/wcdrawlab/research/inplay_eval.py) |
| **Composite objective** | The fixed evaluator's single score: **0.40 x RPS + 0.25 x log-loss + 0.20 x draw-Brier + 0.15 x draw calibration error**. | Weights in [`configs/research.yaml`](../configs/research.yaml); formula in `composite_score` in `runner.py`; contract in [`program.md`](../program.md) |
| **dRPS / paired delta** | Per-match metric difference, candidate minus reference, averaged. Reported with a bootstrap 95% CI. | [`scripts/tier2_baselines.py`](../scripts/tier2_baselines.py), [`scripts/prospective_benchmark_v1.py`](../scripts/prospective_benchmark_v1.py) |

---

## 4. Evaluation terms

| Term | Meaning | Defined in |
|---|---|---|
| **Fixed evaluator** | The evaluation harness the research agent may not edit. It splits folds by time, strips forbidden columns before the candidate sees data, and hard-codes `promoted = False` pending human review. | [`runner.py`](../src/wcdrawlab/research/runner.py), [`program.md`](../program.md), [`AUTORESEARCH_GOVERNANCE.md`](AUTORESEARCH_GOVERNANCE.md) |
| **Dev folds** | World Cup group stages 2010, 2014 and 2018, each predicted by a model trained only on earlier tournaments. 144 pooled matches. Model *selection* happens here and nowhere else. (The fixed evaluator's own fold list in `configs/research.yaml` is 2018, 2022 and the locked 2026 fold; the stricter dev / gate split was introduced by the Tier-2 protocol after an internal audit found that earlier selection had touched 2022.) | [`tier_2_baseline_gate.md`](../notes/research/tier_2_baseline_gate.md), [`tier_2_existing_work_audit.md`](../notes/research/tier_2_existing_work_audit.md) |
| **Release gate** | The 2022 World Cup group stage (48 matches). Under the Tier-2 protocol it is read **once** after selection and not used for tuning. Earlier research cycles had included 2022 in their sweeps; an internal audit caught that, and selection was re-established on the dev folds only. | `tier_2_baseline_gate.md`, [`tier_2_existing_work_audit.md`](../notes/research/tier_2_existing_work_audit.md) |
| **Locked fold** | 2026 World Cup matchday 1 (24 matches), marked `locked: true`. A transfer check only. Its score was printed next to the selection folds in early research cycles, so it was seen more than once; the notes record that it was never used to choose anything. | [`configs/research.yaml`](../configs/research.yaml) |
| **Promotion rule** | A candidate replaces B1 only if its paired-bootstrap delta vs B1 has a 95% CI excluding zero on the dev folds, with no regression on the release gate. The autoresearch config also sets a minimum *relative* composite improvement of 0.002 and a 0.001 per-fold regression tolerance; the batch script applies them, while the fixed evaluator itself never promotes. No candidate met the rule. | [`approved_model_registry.md`](../notes/research/approved_model_registry.md), `configs/research.yaml`, [`scripts/autoresearch_batch.py`](../scripts/autoresearch_batch.py) |
| **Prequential** | "Predict, then learn": each finished match is predicted by a model trained only on matches that kicked off strictly before it. The 33-match 2026 prequential run had a bug on the V8 side (erratum E1); use only the corrected figures in the model card. | [`scripts/prequential_2026.py`](../scripts/prequential_2026.py), [`ERRATA.md`](ERRATA.md) |
| **LOCO** | Leave-one-competition-out: hold out a whole tournament, train on the others. | [`inplay_multicompetition_results.md`](../notes/research/inplay_multicompetition_results.md) |
| **LOGO** | Leave-one-group-out. In the first in-play sprint the "group" is a World Cup group (A-H, 8 folds). Some later in-play notes write "LOGO" with the *competition* as the group, which is the same thing as LOCO. | [`INPLAY_EVALUATION_PROTOCOL.md`](INPLAY_EVALUATION_PROTOCOL.md) |
| **Forward-chain** | Order tournaments by date; train on the earlier ones, test on the next. Respects time, unlike LOCO. | [`dynamic_eval.py`](../src/wcdrawlab/research/dynamic_eval.py) |
| **Nested CV** | Two loops. The inner loop picks a model using only the training competitions; the outer loop scores that pick once on the held-out competition. Removes selection-on-test. | [`inplay_nested_evaluation.md`](../notes/research/inplay_nested_evaluation.md) |
| **Selection-on-test** | Choosing a "best" model after looking at test results, even when each model's parameters were fitted on training data only. The lab caught itself doing this in-play and relabelled the affected claims. | [`inplay_evaluation_reconciliation.md`](../notes/research/inplay_evaluation_reconciliation.md) |
| **Match-level bootstrap** | Confidence intervals from resampling whole *matches*, never individual rows, because snapshots from one match are not independent. 2,000 resamples in the Tier-2 baseline gate and the in-play protocol; 5,000 in the prospective benchmark. | [`INPLAY_EVALUATION_PROTOCOL.md`](INPLAY_EVALUATION_PROTOCOL.md), [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](../notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md) |
| **Primary snapshot rule** | One snapshot per fixture: the latest pre-kickoff snapshot where all five models and the market are present (T-15, else T-90, else baseline, else exclude). Pre-specified and outcome-independent. It was written down on 2026-06-29, after the matches were played but, by the file's own statement, before any model-versus-outcome metric was computed. That ordering is self-attested: the rule, the script and the results share one commit, and there is no external registration. | [`prospective_score_harvest_preregistration.md`](../notes/research/prospective_score_harvest_preregistration.md) |
| **Tier A-D** | The lab's own sample-size labels for the prospective benchmark: A fewer than 10 fixtures ("smoke test"), B 10-19 ("descriptive"), C 20-49 ("exploratory"), D 50 or more ("confirmatory"). The benchmark reached Tier C: 34 scored fixtures, against a market comparator that is mostly an early line (erratum E2). Not a generic evidence grade, and no tier promotes a model. | [`SCORE_HARVEST_GUIDE.md`](SCORE_HARVEST_GUIDE.md), harvester source |
| **Tier 1 / 2 / 4** | Research phases, unrelated to Tier A-D: Tier 1 data layer, Tier 2 baseline gate, Tier 4 in-play sprint. | [`tier_1_completion.md`](../notes/research/tier_1_completion.md), `tier_2_baseline_gate.md`, [`tier_4_sprint_1_completion.md`](../notes/research/tier_4_sprint_1_completion.md) |
| **Power analysis** | Simulation of how many *matches* are needed to detect a given RPS gain. Adding snapshots to the same matches does not add power. | [`international_event_lake_power_analysis.md`](../data/reference/international_event_lake_power_analysis.md) |
| **Leakage guard** | Forbidden post-match columns (score, outcome, post-match xG, post-kickoff odds) are dropped before a model sees data, and tests check it. The repo is leakage-*tested*, not leakage-proof. | `leakage_guard` in `configs/research.yaml`; [`tests/test_research_leakage.py`](../tests/test_research_leakage.py) |

---

## 5. Governance and status vocabulary

| Term | Meaning | Defined in |
|---|---|---|
| **approved** | `approval_status` of exactly one model, B1. Only an approved model may drive a displayed forecast or any downstream decision input. | [`schemas/model_identity_v1.yaml`](../schemas/model_identity_v1.yaml), [`configs/approved_models.yaml`](../configs/approved_models.yaml) |
| **shadow** | Predictions are produced and logged for comparison only. Carries the restrictions `shadow_only, no_decisions, no_risk, no_kalshi, no_approved_ledger, no_performance_claims`. | `configs/approved_models.yaml` |
| **rejected** (identity registry) | `approval_status` of in-play M3 and M4. | `schemas/model_identity_v1.yaml` |
| **production / research_only** | The two `research_status` values. Only B1 is `production`. | `schemas/model_identity_v1.yaml` |
| **runtime_eligible / trade_eligible** | Boolean flags. Exactly one model is runtime-eligible (B1). **No model is trade-eligible.** A validator and tests enforce both. | [`model_identity.py`](../src/wcdrawlab/research/model_identity.py), [`tests/test_model_identity.py`](../tests/test_model_identity.py) |
| **reference_only** | Decision-ledger verdict: the model is a baseline, or a candidate that did not improve on the reference under the locked rules. The reference is kept. It is also B1's verdict in the prospective ledger, where B1 is the reference and cannot be promoted. | [`dynamic_eval.py`](../src/wcdrawlab/research/dynamic_eval.py) |
| **rejected** (decision ledger) | In the dynamic in-play phase: the candidate broke a safety rule (calibration got worse, or a club-test or xG-integrity check failed). The residual goal-intensity ledger also uses it for intensity and horizon candidates that simply did not improve on their reference. | `dynamic_eval.py`, [`residual_goal_intensity_decision_ledger.csv`](../data/reference/residual_goal_intensity_decision_ledger.csv) |
| **data_insufficient** | Not enough data to fit or judge: for example, fewer than 150 positive events, or fewer than 20 fixtures. The event-lake completion report also prints this word as a packaging default, although its per-model ledger records ten `reference_only` verdicts (erratum E6). | `dynamic_eval.py`, [`prospective_benchmark_v1.py`](../scripts/prospective_benchmark_v1.py) |
| **research_candidate_for_future_shadow_review** | The only "positive" verdict the ledgers allow. **No model holds it in any tracked ledger.** | `dynamic_eval.py` |
| **no_evidence_of_improvement** | Prospective verdict for the three blends: no paired delta against both B1 and the market excludes zero at this sample size (34 fixtures, early-line market). It means "no evidence of improvement", not "no effect". | `prospective_benchmark_v1.py`, [`prospective_model_decision_ledger.csv`](../data/reference/prospective_model_decision_ledger.csv) |
| **market_comparator_only** | Prospective verdict for `M2_market`: a read-only benchmark, never a candidate. | `prospective_benchmark_v1.py` |
| **exploratory_underpowered** | Prospective verdict reserved for a nominal improvement at Tier C. Defined in code; not assigned to any model. | `prospective_benchmark_v1.py` |
| **In-play result statuses** | Validity label on each in-play claim: `valid_nested_cross_validation`, `valid_leave_one_competition_out`, `exploratory_transfer_analysis`, `invalid_due_to_training_leakage`, `invalid_due_to_model_selection_on_test_set`, `historical_reference_only`. | [`inplay_result_status_registry.yaml`](../notes/research/inplay_result_status_registry.yaml) |
| **Evidence claim statuses** | `verified_current`, `verified_historical`, `contradicted`, `incomplete`. One of the lab's own coverage claims is marked `contradicted`. | [`research_evidence_registry.csv`](../data/reference/research_evidence_registry.csv) |
| **Freeze manifest** | A JSON record pinning a model's constants, the git commit and SHA-256 hashes of the model and scorer code, written before scoring. | [`final_holdout_freeze_manifest_v2.json`](../notes/research/final_holdout_freeze_manifest_v2.json) |
| **Fail-closed** | On doubt, refuse. The runtime forecaster raises on any unknown or shadow model id instead of falling back. Applies to the *forecaster* path; see the model card for the trading-path nuance. | [`runtime/model_registry.py`](../src/wcdrawlab/runtime/model_registry.py), [`runtime/forecaster.py`](../src/wcdrawlab/runtime/forecaster.py) |
| **Agent-editable file / protected paths** | The research agent may edit one model file, `candidate.py`. Trading, provider, scraping and credential paths are off limits. | [`program.md`](../program.md) |
| **Internal audit / review** | A check carried out by the same human-directed AI agent workflow that built the lab. Not a third-party review. | [`ERRATA.md`](ERRATA.md) |
| **Paper-only** | Forecasts are scored; nothing is staked. No order was ever placed and results are forecast-quality metrics, never P&L. | [`MODEL_CARD.md`](MODEL_CARD.md) |

---

## 6. Operations terms (2026 prospective collection)

| Term | Meaning | Defined in |
|---|---|---|
| **Shadow collector** | A bounded single-cycle script run by the OS scheduler every 5 minutes. It fetches odds within a budget, freezes pre-kickoff predictions, and halts (exit code 3) unless `KALSHI_ENABLE_LIVE_TRADING=false` and `TRADING_MODE=paper`. | [`scripts/windows/shadow_collector_cycle.py`](../scripts/windows/shadow_collector_cycle.py), [`DURABLE_COLLECTOR_AND_SCHEDULER.md`](DURABLE_COLLECTOR_AND_SCHEDULER.md) |
| **Snapshot windows** | When odds are captured. **T-15**: a kickoff is 10-20 minutes away. **T-90**: a kickoff is 80-100 minutes away. **baseline**: anything else, taken at most once per 120 minutes as a sparse fallback. The benchmark's window counts include a fourth label, `final_pre_kickoff` (2 of the 34 primary snapshots; 31 are baseline and 1 is T-90). | `due_snapshot_type` in the collector. [`operations/windows.py`](../src/wcdrawlab/operations/windows.py) is a separate capture-plan helper that defines T-90 and T-15 as a target time plus a grace period. |
| **Early line vs closing line** | A closing line is the last price before kickoff. The 2026 benchmark's market comparator is mostly an **early line**: for 31 of 34 fixtures it is a baseline snapshot from 2026-06-21, a median of about 98 hours before kickoff, because of erratum E2. B1's forecast was frozen at the same early time. No comparison against closing prices was made. | [`ERRATA.md`](ERRATA.md#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger) |
| **No-vig** | Bookmaker odds converted to probabilities with the bookmaker margin removed, so they sum to 1. | [`src/wcdrawlab/market.py`](../src/wcdrawlab/market.py) |
| **First-write-wins ledger** | An append-only JSONL file. Once a prediction is written under a key it is never overwritten, so it stays a true point-in-time forecast even if the collector re-runs after the result is known. | [`operations/ledger.py`](../src/wcdrawlab/operations/ledger.py) |
| **Odds budget** | A persistent guard on The Odds API: hard ceiling of 500 credits and at least 10 minutes between requests. The scheduled collector spent 47 credits; because of erratum E2, none of those 47 snapshots reached the prediction ledger. | [`operations/odds_budget.py`](../src/wcdrawlab/operations/odds_budget.py) |
| **Harvester** | The independent, idempotent, append-only scorer written after the collector's own score step was found to be silently scoring nothing. It refreshes verified-final results itself and makes no Odds API calls. | [`scripts/prospective_score_harvester_v1.py`](../scripts/prospective_score_harvester_v1.py), [`SCORE_HARVEST_GUIDE.md`](SCORE_HARVEST_GUIDE.md) |
| **Score key** | `prediction_id \| result_hash \| scorer_version`. One scored row per key, first write wins. A corrected result has a new hash, so it is appended rather than overwriting. | `build_scored_rows` in the harvester |
| **Verified final** | A result is scored only once the results provider reports a final match status (`reconciliation_status = verified_final`). 35 of 35 predicted fixtures reached this state. | [`scripts/refresh_prospective_final_results.py`](../scripts/refresh_prospective_final_results.py) |
| **`no_common_market_snapshot`** | Exclusion reason for the one fixture (of 35) that had no pre-kickoff snapshot covering all five models and the market. | [`prospective_score_harvest_preregistration.md`](../notes/research/prospective_score_harvest_preregistration.md) |
| **Event lake** | A content-addressed, hash-checked local store of StatsBomb Open Data event files. It lives on the author's disk and is not redistributed. | [`international_event_lake.py`](../src/wcdrawlab/research/international_event_lake.py) |

---

## 7. Common abbreviations

| Term | Meaning |
|---|---|
| **1X2**, **W/D/L** | The three-way match result: home or team A win, draw, away or team B win. |
| **MD1, MD2, MD3** | Group-stage matchdays 1-3. |
| **OOS** | Out-of-sample: scored on data the model never saw. |
| **E1-E7** | The numbered entries in [`ERRATA.md`](ERRATA.md): known defects and corrections. "Erratum E2" in this glossary means entry E2 there. |
| **CI** | Confidence interval. 95% bootstrap intervals unless stated otherwise. |
| **xG** | Expected goals: a shot-quality estimate of how many goals a team "should" have scored. |
| **Elo** | A rating that rises after wins and falls after losses. The research Elo behind B1 is rebuilt walk-forward from historical internationals, using only matches played strictly before each kickoff, with hand-set constants (K = 40, scale 400, home advantage 65 for non-neutral matches, a goal-difference multiplier); see [`tier_1_data_card.md`](../notes/research/tier_1_data_card.md) and [`scripts/build_research_table.py`](../scripts/build_research_table.py). [`ELO_UPDATE_SYSTEM.md`](ELO_UPDATE_SYSTEM.md) documents a separate v0.1 live-update command with different defaults (K = 60, no home advantage). |
| **Own-goal convention** | Whether a provider attributes an own goal to the scorer's team or the team that benefits. Getting this wrong caused a real bug; see [`event_semantics.py`](../src/wcdrawlab/research/event_semantics.py). |
