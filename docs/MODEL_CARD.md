# Model card: B1 ternary Elo

**Research-only. Paper-only. Not betting or financial advice.**
Last updated 2026-09-20. This card replaces the v0.1 scaffold card, which described design
intentions rather than the model that was actually approved and evaluated.

Unfamiliar term? See the [glossary](GLOSSARY.md). Known defects are listed in [ERRATA.md](ERRATA.md).

## At a glance

- **One model is approved: B1**, a three-way (win / draw / loss) Elo model with no fitted
  parameters. Everything else in the repository is shadow-only or research-only.
- B1 was approved because **no alternative improved on it with statistical significance** on the
  development folds. That is a statement about the alternatives and the sample size. It is not a
  claim that B1 is strong in absolute terms.
- In the one prospective test (34 World Cup 2026 group fixtures), there is **no evidence at this
  sample size** that B1, a bookmaker consensus or any of three fixed blends differs from the others.
  None of the 24 reported paired differences has a 95% confidence interval that excludes zero.
- That bookmaker consensus was an **early line** (for 31 of 34 fixtures, a median of about 98 hours
  before kickoff), not a closing line. No comparison against closing prices exists.
- Every sample here is small. Read every number with its sample size and interval.
- No order was ever placed. All results are forecast-quality metrics, never P&L.

---

## 1. Model details

### The approved model

| Field | Value |
|---|---|
| Name | B1, "Elo-only three-way model (ternary Elo, r = 0.4)" |
| Identifiers | `B1_ELO` (runtime registry), `prematch.b1_elo` (canonical), `M1_B1` (2026 shadow study) |
| Implementation | `wcdrawlab.models.baselines.TernaryEloModel`, which calls `ternary_elo_probs` in [`src/wcdrawlab/ratings.py`](../src/wcdrawlab/ratings.py) |
| Version | 1.0.0 |
| Input | One feature: `elo_delta`, the pre-match Elo rating gap between the two teams |
| Output | Three probabilities for the regulation-time result: team A win, draw, team B win |
| Fitted parameters | None. The draw parameter r = 0.4 is hand-set and was never tuned. The Elo ratings that feed it also use hand-set constants (see "How it works") |
| Approved | 2026-06-21, pinned to commit `e78cde4` (tag `tier-1-complete`); governance tag `approved-b1-runtime` |
| Source of truth | [`configs/approved_models.yaml`](../configs/approved_models.yaml), enforced by [`src/wcdrawlab/runtime/model_registry.py`](../src/wcdrawlab/runtime/model_registry.py) |
| Approval evidence | [`notes/research/tier_2_baseline_gate.md`](../notes/research/tier_2_baseline_gate.md), [`notes/research/approved_model_registry.md`](../notes/research/approved_model_registry.md) |
| Licence | MIT (code only; no dataset is redistributed) |

### How it works

Let `p` be the standard Elo expected score for team A given the rating gap. Then:

```text
P(A wins) = p^2       + r * p * (1 - p)
P(B wins) = (1 - p)^2 + r * p * (1 - p)
P(draw)   = 1 - P(A wins) - P(B wins) = (2 - 2r) * p * (1 - p)
```

With r = 0.4 the draw probability is `1.2 * p * (1 - p)`. It peaks at 0.30 for two equally rated
teams and shrinks as the gap grows. **B1 can never give a draw more than 30%.**

The Elo ratings are rebuilt walk-forward from historical international results (49,482 matches in
the source dataset at build time), and each match uses only results from strictly before its
kickoff. The rating update uses hand-set constants: K = 40, scale 400, a home advantage of 65 points
for non-neutral matches, and a goal-difference multiplier. B1 itself adds no home or host term; its
only input is the rating gap. See [`tier_1_data_card.md`](../notes/research/tier_1_data_card.md) and
[`scripts/build_research_table.py`](../scripts/build_research_table.py).

Two footnotes on "no fitted parameters":

- An early research cycle compared alternative Elo constructions (importance weighting, other K and
  home-advantage values) on the 2018 and 2022 folds and **kept the existing default**
  ([`20260620_cycle_2.md`](../notes/research/20260620_cycle_2.md)). The constants were not changed
  by that comparison, but the comparison did look at 2022.
- The function's own docstring says r "should be fitted, not trusted" and calls the decomposition a
  benchmark, not a final model. r was never fitted. That is an accurate description of B1's role
  here: a transparent reference that richer models did not improve on with significance.

[`ELO_UPDATE_SYSTEM.md`](ELO_UPDATE_SYSTEM.md) describes a different thing: the v0.1 live-update
command, whose defaults (K = 60, no home advantage) are not the research Elo used for B1.

### How it was built

The lab was human-directed, with an AI coding and research agent (Claude Code) doing the
implementation under a written governance contract ([`program.md`](../program.md)): a fixed
evaluator, one agent-editable model file, and protected trading, provider and credential paths.
The "reviews" and "audits" mentioned in the research notes are **internal** agent audits. There has
been no third-party or peer review.

### Other models and their status

From [`configs/approved_models.yaml`](../configs/approved_models.yaml) and
[`schemas/model_identity_v1.yaml`](../schemas/model_identity_v1.yaml). The registry enforces two
invariants, checked by [`tests/test_model_identity.py`](../tests/test_model_identity.py): exactly one
model is runtime-eligible (B1), and **no model is trade-eligible**.

| Model | What it is | Status | Why it is not approved |
|---|---|---|---|
| `V8_ELO_BLEND_LOGIT` | Standardized logit blended 0.85 with ternary Elo ([`candidate.py`](../src/wcdrawlab/research/candidate.py)) | shadow | No significant dev-fold improvement over B1. The registry file also cites a "worse than B1 on 2026" result; **that number is a known artifact** (see [Errata](#8-errata)). |
| `MARKET_ELO_BLEND` | 0.6 x no-vig market + 0.4 x ternary Elo | shadow | Cannot be backtested across folds: timestamped odds do not exist before 2020. |
| `prematch.market_novig` (`M2_market`) | No-vig bookmaker consensus | shadow, comparator only | A read-only benchmark, never a candidate. |
| `prematch.elo_market_blend_75_25`, `_50_50`, `_25_75` (`M3`-`M5`) | Fixed B1 / market blends; weights never tuned | shadow | `no_evidence_of_improvement` at n = 34, against an early-line market (see [5a](#5a-prospective-2026-benchmark-the-headline-result-is-a-null)). |
| B0, B2-B7 | Pre-match baseline suite | research only | None improved on B1 with significance on the dev folds; B0 and B2 were significantly worse. |
| In-play M0, M1, M2, M5, M6 | In-play win/draw/loss ladder | shadow, research only | No frozen in-play model was ever scored prospectively. After the first in-play sprint the lab's own verdict was that no model was suitable for a live shadow test. |
| In-play M3, M4 | Goal-within-5-minutes and next-goal-team models | rejected | On 48 matches M3 did not improve on its base rate (Brier 0.1148 vs 0.1126). M4 did only modestly (log-loss 1.032 vs 1.084), with no significance test. |
| Research families W, R, P, X, e, q, h, y, r, i, T | Later in-play research lines | research only | Zero candidates promoted in any tracked decision ledger. The T-family (club-to-international transfer) ledger is missing and that run is null / untested (erratum E5). |

---

## 2. Intended use

- **Forecasting research**: a transparent reference that any richer World Cup group-stage model
  should be compared against, with paired bootstrap intervals.
- **Methodology study**: a worked example of a fixed evaluator, time-ordered folds, immutable
  prediction ledgers, and keeping null and negative results.
- **Teaching and replication**, for readers who obtain the underlying public datasets themselves.

## 3. Out-of-scope uses

- **Betting, trading or any financial decision.** Nothing in this repository is betting or
  financial advice, and nothing here shows that these forecasts would make money.
- Knockout matches. Extra time and penalty shoot-outs are not modelled, and no knockout match was
  collected or scored.
- Club football, women's football, youth football, or friendlies. B1 was only evaluated on men's
  World Cup group-stage matches.
- In-play or live decisions. The in-play models are separate, research-only, and were never scored
  prospectively.
- Any use that needs team news, line-ups, injuries, weather or market information. B1 sees none of it.
- Current forecasts. Active research ended on 2026-06-29; ratings and data have not been maintained since.

---

## 4. Evaluation data

| Dataset | Size | Role | Source note |
|---|---|---|---|
| World Cup group-stage modelling table | 369 played matches, 1998-2026 (48 per tournament for 1998-2022, plus 33 from 2026 at build time) | Training and all historical folds | [`tier_1_data_card.md`](../notes/research/tier_1_data_card.md) |
| Dev folds | 2010, 2014, 2018 group stages; 144 pooled matches | Model selection and the approval decision | [`tier_2_baseline_gate.md`](../notes/research/tier_2_baseline_gate.md) |
| Release gate | 2022 group stage; 48 matches | Read once under the Tier-2 protocol. Earlier cycles had included 2022 in sweeps; an internal audit caught this and selection was redone on the dev folds only | same, plus [`tier_2_existing_work_audit.md`](../notes/research/tier_2_existing_work_audit.md) |
| Locked fold | 2026 matchday 1; 24 matches | Transfer check. Its score was reported in early cycles but, per the notes, never used for selection | [`configs/research.yaml`](../configs/research.yaml) |
| 2026 prequential | 33 finished 2026 group matches | Predict-then-learn replay | [`scripts/prequential_2026.py`](../scripts/prequential_2026.py) |
| 2026 prospective benchmark | 35 fixtures with frozen pre-kickoff predictions; 34 scored, 1 excluded (`no_common_market_snapshot`) | The only truly prospective test | [`PROSPECTIVE_SHADOW_SCORECARD_V1.md`](../notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md) |
| 2022 market study | 48 group matches with pre-kickoff no-vig odds (about 94 minutes before kickoff) | Retrospective comparison with the market | [`market_shadow_evaluation_2022.md`](../notes/research/market_shadow_evaluation_2022.md) |

Match results come from public datasets and football-data.org; odds come from The Odds API.
Sources and licences are described in [`DATA_SOURCES.md`](DATA_SOURCES.md). **None of these datasets
is in the repository** (see [limitations](#6-known-limitations)).

---

## 5. Metrics and results

Lower is better for every metric. RPS is the ranked probability score. A paired delta is
*candidate minus reference*, so negative favours the candidate. Definitions and code locations are
in the [glossary](GLOSSARY.md#3-metrics).

### 5a. Prospective 2026 benchmark (the headline result is a null)

34 scored fixtures, one snapshot per fixture, 5,000-resample match-level bootstrap. The lab's own
sample-size label is Tier C, "exploratory". 680 immutable ledger rows; 35 of 35 results verified final.

| Model | RPS [95% CI] | Log-loss [95% CI] | Draw-Brier [95% CI] |
|---|---|---|---|
| **B1** (`M1_B1`) | 0.1304 [0.0891, 0.1771] | 0.7754 [0.5857, 0.9860] | 0.1833 [0.1059, 0.2693] |
| Market (`M2_market`) | 0.1360 [0.0982, 0.1770] | 0.7740 [0.6070, 0.9521] | 0.1765 [0.1026, 0.2549] |
| 75/25 blend (`M3`) | 0.1304 [0.0909, 0.1762] | 0.7712 [0.5874, 0.9733] | 0.1812 [0.1076, 0.2639] |
| 50/50 blend (`M4`) | 0.1314 [0.0937, 0.1742] | 0.7697 [0.5943, 0.9596] | 0.1793 [0.1074, 0.2611] |
| 25/75 blend (`M5`) | 0.1333 [0.0945, 0.1756] | 0.7707 [0.6000, 0.9543] | 0.1778 [0.1056, 0.2611] |

How to read it:

- B1 is nominally better on RPS. The market is nominally better on log-loss and draw-Brier. The
  intervals overlap almost completely.
- The paired RPS difference, market minus B1, is **+0.0057 with 95% CI [-0.0118, +0.0226]**.
- **Zero of the 24 reported paired deltas** (21 distinct comparisons; three are mirrored) has a 95%
  interval excluding zero.
- Conclusion: no evidence at this sample size that B1 or any blend is better than the market, or
  the reverse. Nothing was ranked and nothing was promoted.

**Mandatory caveat: the market comparator is an early line, not a closing line.** For 31 of the 34
fixtures the snapshot used is a "baseline" capture from 2026-06-21, a median of about 98 hours before
kickoff (2 fixtures used a final pre-kickoff snapshot and 1 a T-90 snapshot). The cause is erratum E2:
a key mismatch meant later odds captures never reached the prediction ledger. B1's forecast was
frozen at the same early time, so both sides of the comparison are early forecasts. A comparison
against closing prices was never made, and this null says nothing about one.

The rule that picks one snapshot per fixture was pre-specified and does not depend on outcomes. It
was written down on 2026-06-29, after the matches were played but, by the file's own statement,
before any model-versus-outcome metric was computed. That ordering is **self-attested**: the rule,
the script and the results share one commit. See
[`prospective_score_harvest_preregistration.md`](../notes/research/prospective_score_harvest_preregistration.md).

Calibration, descriptive only: the observed draw rate was 0.265 against a mean predicted draw
probability of 0.21-0.22. With about 9 draws in 34 matches that gap is within roughly one binomial
standard error, so it is not a finding. Top-label ECE ranged from 0.074 (`M5`) to 0.135 (B1) on 34 samples.

### 5b. Historical folds (why B1 was approved)

Paired bootstrap against B1 on 144 pooled dev matches, 2,000 resamples. The composite is
0.40 x RPS + 0.25 x log-loss + 0.20 x draw-Brier + 0.15 x draw calibration error.

| Model | Dev-mean composite | dRPS vs B1 [95% CI] | Different from B1? |
|---|---|---|---|
| **B1 ternary Elo** | **0.3553** | reference | reference |
| B4 Poisson | 0.3569 | +0.0006 [-0.0050, +0.0061] | no |
| B5 Dixon-Coles style | 0.3580 | +0.0008 [-0.0048, +0.0066] | no |
| B7 calibrated ensemble (no market) | 0.3590 | +0.0011 [-0.0059, +0.0077] | no |
| B3 Elo + host | 0.3634 | +0.0027 [-0.0101, +0.0158] | no |
| B2 FIFA-only | 0.3968 | +0.0237 [+0.0035, +0.0426] | yes, worse |
| B0 frequency prior | 0.4187 | +0.0570 [+0.0301, +0.0851] | yes, worse |

This result is about the **pooled dev folds only**. On the two folds held out of selection, B1 was
mid-table or lower by composite:

| Fold | B1 composite | B1 rank | Best model on that fold |
|---|---|---|---|
| 2022 release gate (48 matches) | 0.416 | **5th of 9** | B2 FIFA-only, 0.387 |
| 2026 matchday 1, locked (24 matches) | 0.427 | 6th of 7 | B5, 0.398 |

Single-fold rankings on 24-48 matches are noisy, and they were not used for selection. They are
shown here so that B1 is not mistaken for "best everywhere".

### 5c. 2022 retrospective market study (suggestive, not replicated)

48 group matches with real pre-kickoff no-vig odds, 2,000-resample paired bootstrap.

- The market alone had the best point RPS and log-loss: 0.2244 / 1.0366 against B1's 0.2435 / 1.1217.
  The paired interval against B1 **includes zero**: dRPS -0.0191 [-0.046, +0.005].
- Of three fixed blends declared in advance, the 75/25 B1/market blend had an RPS interval that
  just excludes zero, dRPS -0.0067 [-0.013, -0.0005], and its log-loss interval also excluded zero.
  The 50/50 blend's log-loss interval excluded zero; its RPS interval did not.
- The source note calls this "suggestive": one tournament, several comparisons with no
  multiple-comparison correction, no blend weight selected, nothing promoted.
- It did not replicate prospectively. In 2026 the same 75/25 blend against B1 gave an RPS delta of
  +0.0001 [-0.0044, +0.0042] (n = 34, early-line market).

### 5d. V8 candidate on the 2026 prequential (corrected)

On the same 33 finished 2026 matches, after the erratum E1 fix:

| Model | RPS | Log-loss | Draw calibration error |
|---|---|---|---|
| V8 | 0.173 | 0.948 | 0.175 |
| B1 | 0.174 | 0.958 | 0.178 |

The point estimates are effectively tied. No confidence interval was computed for this replay. For
scale, even the tightest paired RPS interval in the prospective benchmark (75/25 blend vs B1, n = 34)
is about +/-0.004, so a 0.001 gap on 33 matches should be read as no difference shown.

V8 stays shadow-only for the valid reason: it showed no significant dev-fold improvement over B1.
B1's own figures were never affected by the bug.

---

## 6. Known limitations

1. **Small samples everywhere.** 48 matches per World Cup fold (roughly 10-13 draws each), 144 pooled
   dev matches, 24 in the locked fold, 33 in the prequential, 34 in the prospective benchmark
   (about 9 draws). Differences between serious models are inside the noise. For scale, the lab's own
   power analysis on 231 in-play matches estimated that detecting a 0.005 absolute RPS gain with 80%
   power needs on the order of 1,200 matches. That figure uses in-play noise levels; no separate
   pre-match power calculation was done.
2. **Approved does not mean strong.** B1 holds its place because nothing improved on it with
   significance on the dev folds. It ranked 5th of 9 on the single-read 2022 gate and 6th of 7 on
   the locked 2026 matchday-1 fold.
3. **The comparison with the market is unresolved.** In 2022 (n = 48) the market was nominally
   better, with an interval including zero. In 2026 (n = 34) the market snapshot was an early line.
   No closing-line comparison exists.
4. **Draws.** The formula caps the draw probability at 0.30. In 2026 every model predicted fewer
   draws (0.21-0.22) than occurred (0.265), but that gap is within noise at about 9 draws. B1's
   top-label ECE (0.135) was at the high end of the reported range for the five prospective models,
   and its draw calibration error was 0.178 on the 33-match prequential. Both figures are
   descriptive at these sample sizes.
5. **Group stage only.** Knockout rounds were never collected or scored. Forecasts are for the
   regulation-time three-way result.
6. **One input.** No market, line-up, injury, travel or in-play information reaches B1.
7. **Not reproducible from the repository alone.** `data/raw/`, `data/processed/` (except a
   metadata-only provenance file) and `outputs/` are gitignored. Rebuilding the tables needs external
   downloads and provider API keys. On a fresh clone the test suite runs 817 passing tests and skips
   51 that need those datasets; see [`TESTING_AND_DATA_DEPENDENCIES.md`](TESTING_AND_DATA_DEPENDENCIES.md).
   What *is* tracked: code, configs, schemas, research notes, and machine-readable ledgers and
   manifests under [`data/reference/`](../data/reference/).
8. **Self-attested ordering, internal audits.** Pre-specified rules live in the same repository as
   the results, sometimes in the same commit. There is no external registration and no third-party review.
9. **Runtime gating is fail-closed for the forecaster path, not for the whole trading path.** The
   runtime forecaster raises on any unknown or shadow model id instead of falling back. The trading
   scaffold's RiskGate, however, applies its approved-model check only when a `TradeIntent` carries a
   `model_id`, and that field is optional (it defaults to `None`). See
   [`src/wcdrawlab/trading/risk.py`](../src/wcdrawlab/trading/risk.py).
10. **Stale by design.** Active research ran from 2026-06-20 to 2026-06-29. Nothing has been
    retrained, re-rated or re-collected since.

---

## 7. Ethical and safety notes

- **Paper-only.** No order was ever placed. No profit-and-loss figure exists anywhere in the
  repository, and none should be inferred from forecast-quality metrics.
- **Dormant trading scaffold.** [`src/wcdrawlab/trading/`](../src/wcdrawlab/trading/) is a dormant,
  triple-gated paper/demo execution scaffold. It was never armed and never given credentials. The
  production order path raises unless `require_live` is set **and**
  `KALSHI_ENABLE_LIVE_TRADING=true` **and** an exact acknowledgement string is supplied. The 2026
  collector hard-halts (exit code 3) unless `KALSHI_ENABLE_LIVE_TRADING=false` and
  `TRADING_MODE=paper`. The module is kept and labelled rather than deleted, so the history stays honest.
- **Registry wording.** `configs/approved_models.yaml` lists `paper_trade_decision_input`,
  `risk_calculation_input` and `model_performance_claims` among B1's allowed uses. Those are
  permission labels inside the dormant scaffold, not a record of activity, and this card makes no
  performance claim beyond the intervals above. The same file calls B1 "parameter-free"; read that
  as "nothing fitted" (r and the Elo constants are hand-set). The file is governance-protected and
  was left unedited.
- **Not advice.** Sports forecasts are uncertain. A model that could not be told apart from an
  early market line on 34 fixtures says nothing about making money against any market. Gambling
  carries real financial and personal risk.
- **Data rights.** The code is MIT-licensed. Third-party data (match results, odds, event data) keeps
  its own terms and is not redistributed here.

---

## 8. Errata

Full list: [`ERRATA.md`](ERRATA.md). Two entries matter most for this card.

- **[E1](ERRATA.md#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug): the recorded "V8 worse than
  B1 on 2026" numbers are a bug artifact.** The prequential script
  built V8's test row with an all-object dtype, so every feature was zero-filled and V8 emitted
  near-constant forecasts of about 0.35 / 0.31 / 0.34. The recorded figures (RPS 0.225 vs 0.174,
  log-loss 1.092 vs 0.958, and a V8 draw calibration error of 0.004) are **invalid and must not be
  quoted as findings**. The script was fixed on 2026-09-20; the corrected numbers are in
  [section 5d](#5d-v8-candidate-on-the-2026-prequential-corrected).
  **The stale numbers are still quoted in `configs/approved_models.yaml`**, which is
  governance-protected and was deliberately left unedited. Treat that `reason_not_approved` text as
  historical; the valid reason is the absence of a significant dev-fold improvement.
- **[E2](ERRATA.md#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger): the 2026 market
  comparator is an early line.** All 47 odds snapshots taken by the scheduled
  collector were silently ignored because of a payload key mismatch, so every market-bearing
  prediction comes from 9 snapshots taken on 2026-06-21. Fixed on 2026-09-20; the historical ledger
  is unchanged.

---

## 9. Where to check these claims

| Claim | File |
|---|---|
| B1 is the only approved model | [`configs/approved_models.yaml`](../configs/approved_models.yaml), [`tests/test_runtime_governance.py`](../tests/test_runtime_governance.py) |
| One runtime-eligible model, none trade-eligible | [`schemas/model_identity_v1.yaml`](../schemas/model_identity_v1.yaml), [`tests/test_model_identity.py`](../tests/test_model_identity.py) |
| Research Elo constants and the comparison that kept them | [`notes/research/tier_1_data_card.md`](../notes/research/tier_1_data_card.md), [`scripts/build_research_table.py`](../scripts/build_research_table.py), [`notes/research/20260620_cycle_2.md`](../notes/research/20260620_cycle_2.md) |
| Dev-fold bootstrap table and fold rankings | [`notes/research/tier_2_baseline_gate.md`](../notes/research/tier_2_baseline_gate.md) |
| Prospective metrics and all 24 paired deltas | [`notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md`](../notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md), [`notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md`](../notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md) |
| Prospective verdict per model | [`data/reference/prospective_model_decision_ledger.csv`](../data/reference/prospective_model_decision_ledger.csv) |
| 2022 market study | [`notes/research/market_shadow_evaluation_2022.md`](../notes/research/market_shadow_evaluation_2022.md) |
| Corrected V8 prequential figures | [`ERRATA.md`](ERRATA.md#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug), [`scripts/prequential_2026.py`](../scripts/prequential_2026.py) |
| Power analysis (231 in-play matches) | [`data/reference/international_event_lake_power_analysis.md`](../data/reference/international_event_lake_power_analysis.md) |
| Metric definitions | [`src/wcdrawlab/evaluation.py`](../src/wcdrawlab/evaluation.py), [`src/wcdrawlab/research/runner.py`](../src/wcdrawlab/research/runner.py) |
| Governance contract | [`program.md`](../program.md), [`AUTORESEARCH_GOVERNANCE.md`](AUTORESEARCH_GOVERNANCE.md) |
