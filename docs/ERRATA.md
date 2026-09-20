# Errata and known defects

This lab keeps its mistakes on the record. Superseded notes are **bannered, not deleted**, and every
correction below links to the evidence. If you find another error, please open an issue.

Most items here were found on **2026-09-20** by an internal, agent-run, read-only audit of the consolidated
repository (not a third-party review), which re-checked the headline claims against the files they came
from. It corrected a number of claims in the documentation and surfaced two latent bugs (E1, E2) that the
original work had missed for three months.

| ID | What | Severity | Status |
|---|---|---|---|
| [E1](#e1--the-v8-worse-than-b1-on-2026-result-was-a-bug) | A recorded model comparison was produced by a bug | High — a published number was wrong | Code fixed; corrected number below; stale quotes bannered |
| [E2](#e2--47-paid-odds-snapshots-never-reached-the-prediction-ledger) | 47 odds snapshots were silently ignored | High — changes how the headline benchmark must be read | Code fixed; historical ledger unchanged; caveat added everywhere |
| [E3](#e3--the-collectors-own-scoring-step-was-never-repaired) | Collector's own scoring step never repaired | Medium | Patch deliberately deferred; the independent harvester is the scoring path |
| [E4](#e4--early-beats-the-market-notes-were-never-confirmed) | Early "beats the market" notes | High if repeated | Bannered; never confirmed prospectively |
| [E5](#e5--the-hierarchical-transfer-decision-ledger-is-missing) | A null-result ledger is missing | Low | Documented; not fabricated |
| [E6](#e6--two-vocabularies-for-the-same-event-lake-outcome) | Two verdict vocabularies for one outcome | Low | Documented |
| [E7](#e7--stale-manifests-and-machine-specific-paths) | Stale manifests; machine-specific paths | Low | Documented |

---

## E1 — the "V8 worse than B1 on 2026" result was a bug

**What was recorded.** On 33 finished 2026 group matches, scored prequentially, the autoresearch candidate
V8 was reported as clearly worse than plain Elo (RPS 0.225 vs 0.174; log-loss 1.092 vs 0.958) but far
better calibrated on draws (draw-calibration error 0.004 vs 0.178). This was cited as a reason V8 stayed
shadow-only. The same artifact was also one of two stated motivations for raising V8's Elo blend weight from
0.50 to 0.85 in cycle 3 (see the `candidate.py` docstring and `notes/research/20260620_cycle_3.md`, which
describe a "2026 prequential signal"). The other motivation (the 2022 backtest) and the fold sweep did not
depend on this script, and the weight was later re-established on development folds only
(`notes/research/tier_2_existing_work_audit.md`).

**What actually happened.** `scripts/prequential_2026.py` built the candidate's single test row with
`m.to_frame().T`. In pandas that produces an **all-`object`-dtype** frame. The evaluator's
`leakage_safe_feature_frame()` keeps only numeric columns, so it returned *zero* columns, and the following
`reindex(..., fill_value=0.0)` zero-filled **every** feature — including the Elo difference. The "V8" being
scored was therefore a near-constant forecast of about 0.35 / 0.31 / 0.34 for every match, whoever was
playing (for Mexico v South Africa: B1 0.808 / 0.132 / 0.060 vs "V8" 0.348 / 0.306 / 0.346).

Two consistency checks expose it without running anything: RPS is convex, so a genuine
`0.85·B1 + 0.15·logit` blend could only reach 0.225 if the logit leg scored worse than a uniform forecast;
and a draw-calibration error that small is exactly what a constant forecast yields: every prediction falls
in one bin, so the metric collapses to |mean predicted draw − observed draw rate| — 0.022 in the first
recorded run (0.325 vs 0.303, with the 0.50 blend: RPS 0.221 / log-loss 1.082) and 0.004 in the re-run
quoted above (about 0.306 vs 0.303).

**Corrected result** (same script, same 33 matches, fixed 2026-09-20):

| model | RPS | log-loss | draw-Brier | draw-cal |
|---|---|---|---|---|
| V8 candidate | 0.173 | 0.948 | 0.229 | 0.175 |
| **B1 ternary Elo** | 0.174 | 0.958 | 0.232 | 0.178 |

They are **tied**, which is what the dev folds had already shown. B1's own figures were never affected
(B1 reads the Elo difference directly) and reproduce the recorded values exactly. V8 correctly remains
shadow-only, for the valid reason: no significant improvement over B1 on the development folds.

**Still quoting the wrong numbers:** `configs/approved_models.yaml` (`reason_not_approved`) — this file
is governance-protected and was deliberately left unedited — plus `notes/research/prequential_2026.md`,
`approved_model_registry.md`, `runtime_model_governance.md`, `OVERNIGHT_FINAL_REPORT.md`,
`model_state_reconciliation.md` (whose "reproduced within tolerance" reproduced the bug) and
`20260620_cycle_3.md`, plus the cycle-3 docstring in `src/wcdrawlab/research/candidate.py` (left unedited:
it is the frozen candidate file). The notes carry correction banners.

## E2 — 47 paid odds snapshots never reached the prediction ledger

**The defect.** The budget-guarded fetcher `scripts/fetch_odds_live_2026.py` wrote each snapshot's payload
under the key `"events"`. The freezer `scripts/live_2026_shadow.py` read only the key `"data"` — the key
written by a one-off session script on 2026-06-21. Nothing failed; the freezer simply found "no market" and
froze Elo-only rows.

**Measured on the raw files:** 56 snapshots exist — 9 keyed `"data"`, **47 keyed `"events"`** (22 baseline,
16 T-90, 9 T-15; 47 of the 500-credit budget). All 47 were ignored. Every market-bearing prediction in the
ledger comes from the 9 snapshots of 2026-06-21.

**Why it matters.** In the prospective benchmark, the primary snapshot for **31 of 34 fixtures** is an
early "baseline" snapshot (2 are final-pre-kickoff, 1 is T-90); across all 34 scored fixtures the median
lead time is roughly **98 hours before kickoff**. The "no-vig market" in that benchmark is therefore an **early line, not a closing line**, and B1's
forecast is frozen at the same early time. The null result stands; the comparison it describes is weaker
than "model versus closing market", and it is labelled that way throughout this repository.

**Also missed:** the score-harvest root-cause audit (`notes/research/prospective_score_harvest_root_cause_audit.md`)
marked "snapshot parsing" as a *false* cause. It was wrong about that.

**Fix (2026-09-20):** the freezer now accepts either key. The historical ledger is unchanged — nothing was
re-frozen or back-filled.

## E3 — the collector's own scoring step was never repaired

The collector's `score` step returned success every five minutes while scoring nothing: no step in the
cycle refreshed the results file, so 0 of 680 predictions ever resolved a `FINISHED` outcome, and an empty
metrics file was written with exit code 0. Rather than patch a live collector, an **independent,
idempotent, append-only harvester** was built and became the official scoring path
([`SCORE_HARVEST_GUIDE.md`](SCORE_HARVEST_GUIDE.md)). Running the collector alone still writes empty
metrics. See `notes/research/prospective_score_deployment_decision.md`.

## E4 — early "beats the market" notes were never confirmed

`notes/research/20260620_cycle_4.md` reports that a market + ~0.4·Elo blend "robustly beats the no-vig
consensus", and `20260620_cycle_5_true_alpha.md` that it "beats Pinnacle's closing line by ~4% composite /
+4–7% RPS". Those are **retrospective point
estimates** on 253–341 auxiliary internationals, 3 of 4 folds, with **no confidence intervals**. The lab's
own later documents reclassified them as auxiliary (`model_state_reconciliation.md`), the Tier-2 gate found
nothing robustly beats Elo, the model registry places that blend under `no_performance_claims`, and the
prospective benchmark found no separation between any model and the market — and that benchmark's market
is an early line (E2), so it says nothing either way about a *closing* line. The claim is repeated in a few
other early notes and in the archived [`history/VERSION.md`](history/VERSION.md); all carry banners.
**This repository does not claim to beat any market.**

## E5 — the hierarchical-transfer decision ledger is missing

`docs/HIERARCHICAL_DOMAIN_TRANSFER_V1_RUNBOOK.md` and the completion report cite
`data/reference/hierarchical_transfer_decision_ledger.{json,csv}`. The file was cleared during a repair
(commit `29db653`) and never regenerated; a second defect left the run with **0 club training rows**. The
honest summary: no model beat the reference T0, and **cross-domain transfer lift is untested**. The ledger
has not been reconstructed. Note also that `data/reference/hierarchical_transfer_eval_audit.json` has
`dataset: synthetic_self_test` — its numbers are synthetic and must never be quoted as results.

## E6 — two vocabularies for the same event-lake outcome

`INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md` headlines "Verdict: `data_insufficient` /
Reference: None" (a packaging default), while the per-model ledger records ten `reference_only` verdicts.
Both describe one outcome: on the restored 231-match cohort, **no candidate cleared the locked multi-rule
gate**. One model (e9) had a lower leave-one-competition-out RPS with a confidence interval excluding zero,
but failed the log-loss and forward-chain rules and stayed `reference_only`. It is not a positive result.

## E7 — stale manifests and machine-specific paths

- Several `data/reference/` manifests are point-in-time snapshots that disagree with the current
  `corpus_coverage_ledger.json` — see [`../data/reference/README.md`](../data/reference/README.md).
- About 138 tracked files contain the original development machine's absolute paths. In notes and ledgers
  this is historical provenance. In `configs/`, the research-line runners and the `*.ps1` wrappers it means
  those pipelines are **single-machine orchestration records**: the tests run anywhere, but re-running a
  research line elsewhere requires editing its roots config. The prospective harvester
  (`PSH_COLLECTOR_ROOT`), the key loader (`WCLAB_MAIN_ROOT`) and the event-lake safety guard are portable.
- The match-level power projection from the 58-match cohort ("~150 matches for 80% power") used an
  optimistic noise template and is superseded by the 231-match analysis (power 0.28 for a 0.005 RPS gain;
  80% first reached near 1,200 matches).

## Other defects fixed in the 0.3.0 release

These did not change any recorded research result, but a visitor cloning the repository would have hit them.
Details are in the [changelog](../CHANGELOG.md).

- **`wcdrawlab predict-live` crashed** with a `NameError` *after* writing its outputs (a block copied from
  another function referenced undefined names). The test module imported the function but never called it.
- **The event-lake safety guard only worked on the author's machine**: it matched directory *names*, so on
  any other clone a lake root inside the repository was silently accepted. It now checks real path containment.
- **A crash under pandas 3**: under copy-on-write, `to_numpy()` can return a read-only view, and one
  in-place repair of invalid market rows wrote into it. The very first CI run exposed this (Python 3.13 pulls
  pandas 3; Python 3.10 cannot). The suite now passes on pandas 2.3 and pandas 3.0.
- **A clean install ran zero tests**: three research scripts matched pytest's default globs and one imports
  an undeclared package at module scope, aborting collection. Collection is now scoped to `tests/`.
- **Two tests passed vacuously** (a bare `return` when local data was absent). They now skip with a reason,
  so the pass count means what it says.

