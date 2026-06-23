# Final 2026 Prospective Scoring Protocol (Phase 2, frozen 2026-06-22)

This protocol makes future 2026 World Cup matches a **genuine out-of-sample test** by freezing one model
version. It exists because the earlier 2026 "validation" was contaminated by model selection on the test
set (see `inplay_evaluation_reconciliation.md`). research_only=true; B1 remains the sole runtime model;
nothing here trades or influences approved forecasts.

## Frozen object
- **Model:** `m2fit_temp_frozen` — `FrozenInPlayModel` in `src/wcdrawlab/research/final_holdout.py`.
- **Parameters (FIXED):** base=1.1372, k=0.1541, temperature=1.4000 (fit on 151 PRE-2026 matches only).
- **Config:** `configs/final_holdout_model.yaml`; **manifest:** `notes/research/final_holdout_freeze_manifest.json`.
- **FINAL_HOLDOUT_FREEZE_UTC:** 2026-06-22T21:24:39Z (commit `f7b096b`).

## Immutable after the freeze
The following must NOT change for any future-2026 score to count as prospective:
architecture, learned parameters (base, k), temperature, feature definitions
(`inplay_v1`: elo_delta_home, decision_minute, score_home, score_away, red_home, red_away),
pre-match anchor (Elo), allowed data sources (API-Football Pro state + elo_history).

## Scoring rules
1. Each 2026 decision point is predicted from state known **strictly before** its decision timestamp.
2. Predictions are captured **before** the outcome is known (first-write-wins ledger).
3. Outcomes are used **only** to score (RPS / log-loss / calibration). Never to retrain or re-select.
4. **Pristine prospective set** = 2026 matches with kickoff **after** the freeze timestamp. The 30
   already-finished 2026 matches were seen during development and are labelled exploratory, NOT pristine.
5. If the model is ever changed, a NEW freeze (new manifest, new timestamp) starts a fresh prospective
   window; old and new windows are never pooled.

## Determinism + integrity
- `FrozenInPlayModel` performs NO fitting; it reconstructs from the config and scores deterministically
  (unit-tested: identical inputs -> identical outputs; params match the manifest).
- The manifest pins the git commit, `models.py` SHA-256, and scorer SHA-256 so the exact frozen code is
  recoverable.

## v2 RE-FREEZE (2026-06-23) — operative model is now plain M2
Phase 5 nested CV showed the v1 frozen model (`m2fit_temp`) does NOT survive selection (it was crowned
via selection-on-test); plain **M2** is the reference. The operative prospective model is therefore
**`m2_frozen`** (M2 = remaining-time Poisson, base=1.35, k=0.20, no temperature, no fitting):
- config `configs/final_holdout_model_m2.yaml`; manifest `notes/research/final_holdout_freeze_manifest_v2.json`.
- M2 is parameter-free, so **no 2026 result can change it** — the cleanest possible prospective baseline.
- v1 (`m2fit_temp`, `configs/final_holdout_model.yaml`) is **retained as an immutable historical record**,
  not used for prospective scoring.
- Verified: `FrozenInPlayModel(1.35, 0.20, 1.0)` reproduces `M2_RemainingPoisson` exactly.

## This phase builds machinery only
No live collector is launched here. A future phase may run a durable collector that, for each upcoming
2026 fixture, writes frozen predictions to a ledger and scores them once finished — strictly paper,
strictly scoring.
