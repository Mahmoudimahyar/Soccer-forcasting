# Tier 2 — Existing-Work Audit (pre-build, branch `tier-2-pre-match`)

Inspect and account for prior pre-match work before writing new Tier-2 code. No valid artifact
is deleted or overwritten.

## 1. What Tier 2 work already exists?
- **Canonical table builder:** `scripts/build_research_table.py` → `data/processed/research_modeling_table.csv`
  (369 played WC group matches 1998–2026) + `forecast_targets_2026.csv` (39 upcoming).
- **Baseline suite:** `scripts/evaluate_baselines.py` — B0–B7 across dev(2010/14/18)/gate(2022)/locked(2026-MD1).
- **Active candidate:** `src/wcdrawlab/research/candidate.py` — standardized logit on strength +
  group-state, blended 0.85 with ternary-Elo (cycles 1 & 3).
- **Fixed evaluator:** `src/wcdrawlab/research/runner.py` (folds 2018/2022/2026-MD1; strips forbidden cols).
- **Reports:** `notes/research/` cycle 1–6, baseline_evaluation, prequential_2026, forecast/market notes.
- **Outputs (generated):** `outputs/research/baselines/`, `fold_metrics.csv`, `forecasts/`, `prequential_2026.csv`.
- **Aux research thread (NOT WC folds):** international-odds beat-market analysis (cycles 4–5) on
  Euro/Copa/NL/AFCON 2021–2025 — a separate dataset, not the WC Tier-2 baseline.

## 2. Reproducible from tracked code + approved sources?
**Yes, with documented inputs.** `examples/fetch_public_data.py` (martj42 CC0, jfjelstul MIT) +
`scripts/fetch_footballdata_2026.py` (football-data.org, keyed) + `scripts/build_research_table.py`
rebuild the table deterministically. FIFA from the open Dato-Futbol dataset
(`scripts/fetch_fifa_rankings.py`). Odds require the paid Odds API (only 2022 + 2026-live).
The generated table/outputs are gitignored but fully reproducible; provenance + content hashes in
`data/processed/source_provenance.json`.

## 3. Generated vs source-controlled
- **Source-controlled (committed):** all `scripts/`, `src/`, `tests/`, `schemas/`, `configs/`,
  `data/reference/tiebreak_rules_2026.yaml`, `data/processed/source_provenance.json` (force-added),
  seed/live demo CSVs, notes.
- **Generated (gitignored, reproducible):** `data/processed/research_modeling_table.csv`,
  `forecast_targets_2026.csv`, `elo_history.csv`, intl datasets, `data/raw/*`, all of `outputs/`.

## 4. Which B0–B7 already exist?
All implemented in `scripts/evaluate_baselines.py`:
- B0 historical prior · B1 ternary-Elo · B2 FIFA-only logit · B3 Elo+host logit ·
  B4 independent Poisson · B5 Dixon-Coles · B6 no-vig market (function `market.no_vig_from_decimal_odds`) ·
  B7 Platt-calibrated ensemble (B1+B5+general-logit, draw recalibration).
- **B6 caveat:** the WC table carries NO odds (100% missing), so B6 in the WC folds is only
  computable for 2022 (`market_features_2022.csv`); 2018/2010/2014 have none.

## 5. Which metrics were actually computed?
Computed: RPS, 3-way log loss, draw Brier, draw calibration error, composite, accuracy, draw-rate
actual/pred, mean entropy, draw reliability tables, a draw-interval coverage proxy.
**NOT yet computed (Tier-2 requires):** calibration **slope/intercept**, full **interval coverage**,
and **paired bootstrap confidence intervals** for each model delta vs Elo-only. → built in Step 3.

## 6. Which results are valid under current leakage rules?
- The **current** `fold_metrics.csv` / `outputs/research/baselines/*` are from the CORRECTED table
  (per-tournament `group_uid`, strict-before group aggregates, time-safe Elo, forbidden-col strip)
  and pass 61 tests → **valid**.
- The international beat-market OOS result (cycles 4–5) used real pre-kickoff odds with temporal CV
  → valid for that auxiliary dataset, but it is NOT a WC Tier-2 fold result.

## 7. Which results must be discarded / rerun / relabeled?
- **DISCARD:** the very first fixed-evaluator run (composite 0.4253) computed on the buggy
  cross-tournament group-state table — superseded by the corrected build. (Already not relied upon.)
- **RELABEL / re-establish:** the candidate's accepted blend weight (0.85, cycle 3) was chosen via a
  sweep over **2018 + 2022**. 2022 is the Tier-2 **release gate** ("evaluate once, do not repeatedly
  tune"). The prior sweep technically touched the gate. → Tier-2 will **select only on the dev folds
  (2010/14/18)** and read **2022 once** as the gate; the Step-3 suite is the authoritative gate read.
- **MARK UNAVAILABLE:** B6 for 2010/2014/2018 (no odds). Synthetic `data/seed/sample_odds_2026.csv`
  was never used in any metric (table market = all-missing) — correct; keep it labeled demo-only.
- **NEGATIVE (keep, valid):** FIFA features (cycle 2b) and squad value (cycle 6) — redundant with
  Elo/market, no gain. Elo importance-weighting (cycle 2a) — no gain. All honestly recorded.
- **Calibration caution:** the rejected isotonic B7 (exploded the locked fold) is already discarded;
  current B7 uses Platt fit on the **train** split (not test) — acceptable, but Step 3 will switch to
  strict train-fold-only / time-respecting calibration and report held-out calibration.

## 8. Are prior 2026 outputs point-in-time, or retrospective?
- **2026 MD1 fold** (train<2026, locked): genuine **point-in-time** transfer test. ✓
- **`forecast_2026_market_anchored.csv`**: pre-kickoff snapshot (market T-90 + Elo strict-before) for
  the 39 upcoming matches → **point-in-time** forecast. ✓
- **`prequential_2026.csv`**: walk-forward, each match trained only on strictly-earlier data →
  **genuine point-in-time** out-of-sample per match. ✓
- **`advancement_2026*.csv`**: Monte-Carlo **simulations** conditioned on current probabilities —
  scenario calculations, **not** match predictions. Relabeled as simulations (not "predictions").

## Conclusion
Substantial valid Tier-2 work exists and is reproducible. The gaps to close before the gate:
(i) add calibration slope/intercept + interval coverage + paired bootstrap CIs; (ii) re-run the
baseline suite with **dev-only model selection** and a **single** 2022 gate read; (iii) keep B6
strictly to folds with real timestamped odds and give B7 explicit no-market vs market-enabled
variants. These are done in Step 3; the verdict is recorded in `tier_2_baseline_gate.md`.
