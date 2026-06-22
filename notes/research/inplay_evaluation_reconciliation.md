# In-Play Evaluation Reconciliation (Phase 1, 2026-06-22)

Forensic audit of every in-play experiment to date. **No prior reports deleted**; their evaluation
status is relabelled here and in `inplay_result_status_registry.yaml`. The driving concern: across
multiple work turns I repeatedly *looked at* the 2026 World Cup results and then **built `M2fit` and
crowned `M2fit_temp` partly because of those 2026 numbers** — that is model selection on the test set,
even though no single model's *parameters* were fit on 2026.

## Audit questions (A–E)

**A. Did `M2fit` estimate base-rate / Elo-coefficient parameters using any 2026 matches before reporting
2026 performance?**
NO. In `scripts/eval_2026_holdout.py`, `M2fit` is fit on `tr = df[df.competition != "2026_WORLDCUP"]`
(the 5 pre-2026 competitions) and only then predicts 2026. Parameter estimation is leakage-free.

**B. Did temperature scaling fit only on training competitions in every fold?**
YES. `TemperatureScaled.fit(train)` fits T via leave-one-competition-out OOF *within* the training set;
in the 2026 report `train` excludes 2026, and in the LOGO eval each fold's T uses only that fold's
training competitions. No temperature was fit on held-out data.

**C. Did any model / hyperparameter / feature / calibration / ensemble choice use 2026 results before its
reported 2026 score?**
**YES — this is the core problem.** The *sequence* of decisions used 2026:
  1. Ran the 2026 holdout; observed M2/M6 are draw-overconfident and M2temp/M5 calibrate better.
  2. **Because of that 2026 observation**, added temperature scaling and then `M2fit`, then re-ran on 2026.
  3. Crowned **`M2fit_temp` "best" after seeing it won on 2026** (RPS 0.1429).
Each model's parameters were train-only, but the **choice of which models to build and crown was informed
by repeatedly viewing 2026** → selection-on-test / multiple-comparisons peeking. Therefore the 2026
numbers for M2temp / M2fit / M2fit_temp are **exploratory**, not "final out-of-sample validation."

**D. Were all model transformations fit only inside each training fold?**
Within each eval the answer is YES (per-fold `.fit(train)`, OOF temperature). The leakage is NOT inside a
fold — it is at the **across-experiment model-development** level (C).

**E. Were match-level bootstrap intervals computed over held-out matches rather than correlated state
rows?**
YES (correct). `paired_match_bootstrap` reduces per-row deltas to per-**match** means, then resamples
matches. State rows within a match are not treated as independent. (Caveat: the pooled bootstrap mixes
matches across folds; that is acceptable for an aggregate CI but is not a per-competition test.)

## What stands vs what is downgraded

**Still valid (historical, pre-specified, no 2026 selection):**
- Multi-competition **leave-one-COMPETITION-out** on the 5 pre-2026 tournaments (151 matches): M2 & M6
  beat M1 on 5/5; M2 dRPS −0.0145 CI [−0.021,−0.008]. Reported before 2026 data was even built.
- **Market ≈ Elo in-play** (M6 vs M2 CI includes 0) — comparison of two pre-specified anchors.
- **Player-plane pre-match negative** (166 matches, LOGO): genuine negative, no selection pressure toward
  a positive.
- **Temperature scaling improves calibration** as a *general* statistical fact (tempering an
  overconfident model raises its reliability slope) — direction is robust independent of 2026.

**Downgraded to `exploratory_transfer_analysis` (were implicitly treated as OOS validation):**
- `M2fit_temp` / `M2temp` / `M2fit` **"best on the 2026 World Cup"** (RPS 0.1429 etc.). The 2026 numbers
  are real but were used to *select* these models → exploratory, NOT final validation.
- "`M2fit_temp` is the best/recommended in-play model" — the crowning used 2026 peeking.

**Remains valid even on 2026 (pre-specified baselines, not selected on 2026):**
- **In-play (M1) vs static-B1 (M0)** on 2026: M0 and M1 are fixed baselines defined before any 2026 data;
  their comparison (dRPS −0.0447, CI [−0.084,−0.005]) is a legitimate out-of-sample observation that
  in-play >> static. (n=30 matches; treat the magnitude as indicative.)

**Underpowered (not invalid):**
- **Live-xG negative** (2 competitions / 68 matches): valid LOGO *direction* (no gain), but only 2 folds
  → underpowered; treat as exploratory-leaning. 3 W/D/L variants were tried and all reported ns (no
  selection toward a positive).

## Consequence / remedy
- The honest claim is reduced to: **(i) in-play >> static is validated OOS on 2026; (ii) on historical
  LOGO, M2/M6 beat M1; (iii) temperature scaling improves calibration in-sample/historically.** The
  ranking of M2fit_temp as "best" is **exploratory** until confirmed by a clean protocol.
- Phase 5 rebuilds selection as **nested CV using ONLY historical competitions** (no 2026 in selection).
- Phase 2 **freezes** a single model version for genuine *prospective* 2026 scoring, so future 2026
  matches become real out-of-sample (no further peeking-and-rebuilding).
