# Approved Model Registry

Single source of truth for which model is approved. Created by the reconciliation audit
(`notes/research/model_state_reconciliation.md`). No model code was changed to write this.

## APPROVED pre-match model
- **Model:** **B1 — Elo-only three-way model** (`wcdrawlab.models.baselines.TernaryEloModel`, r=0.4),
  consuming the time-safe internal Elo (`elo_before`, strict `< kickoff`).
- **Approved commit:** `e78cde4376605f6e787a375fe12162c3f81240d0` (tag `tier-1-complete`); evaluation
  reproduced at HEAD `0cc9f2d` on branch `tier-2-pre-match`.
- **Source-data version:** snapshots in `data/processed/source_provenance.json` (martj42 `64d75097`,
  jfjelstul `037f7187`, football-data 2026 `e78a688b`, FIFA `d4f4d8d3`; retrieved 2026-06-20).
- **Feature schema:** `elo_delta` only (Elo from `elo_history.csv`; table schema = research_modeling_table v1, 66 cols).
- **Training cutoff:** parameter-free (r=0.4 fixed); Elo uses only matches strictly before each kickoff
  (effective per-match cutoff = kickoff). Dev selection trained through 2009/2013/2017; gate through 2021; locked through 2025.
- **Evaluation report:** `notes/research/tier_2_baseline_gate.md`, `outputs/research/tier2/by_fold.csv`,
  `outputs/research/tier2/bootstrap_vs_elo.csv`.
- **Approval timestamp:** 2026-06-21.
- **Why approved:** Tier-2 paired bootstrap shows **no candidate beats B1 with significance**
  (B7_nomarket dRPS vs B1 = +0.0011, 95% CI [−0.0059, +0.0077]; B0 and B2 significantly worse).
  B1 is also best on DEV-mean composite (0.3553) and reproduces exactly.

## Known limitations of the approved model
- Elo is under-confident vs the market on big mismatches; on the 2026 prequential it has worse draw
  calibration (drawCal 0.178) than V8 (0.004) — it is sharp but not draw-calibrated.
- No market signal (B6 unavailable pre-2020); no in-play/player features.

## NOT runtime-approved (experimental)
- **V8** (`src/wcdrawlab/research/candidate.py`, sha256 `bad84a7d…`): standardized logit + 0.85
  ternary-Elo blend. It is the **autoresearch candidate surface** evaluated by `runner.py`. On the
  2026 prequential it is **worse than B1 on RPS (0.225 vs 0.174) and log-loss (1.092 vs 0.958)**;
  better only on draw calibration. **Not promoted. Not runtime-approved.**
- **Market-anchored blend** (`scripts/market_anchored_forecast.py`, 0.6·market + 0.4·Elo): the
  current live 2026 forecast *generator*. It is an **experimental forecast-aid**, justified only
  prospectively (2022 gate + auxiliary international OOS); it is **not** a cross-fold-validated
  approved model (B6 cannot be validated pre-2020). **Not the approved baseline.**

## No-ambiguity statement on live predictions
- The **model of record / approved baseline is B1 (Elo)**.
- `candidate.py` (V8) is **experimental** — used only by the fixed evaluator for autoresearch, and
  its docstring already labels it the agent-editable autoresearch candidate. It must **not** be
  treated as the approved/runtime model unless separately promoted by beating B1 (bootstrap CI
  excluding 0 on the DEV folds, no 2022-gate regression).
- The market-anchored blend is an **experimental forecast aid**, clearly distinct from the approved
  baseline. Any live/paper prediction must be labeled as either **B1 (approved)** or
  **experimental aid** — never as V8.

## Required governance follow-up (needs explicit approval; not done here — no code changes)
To make runtime unambiguous, choose ONE (a future, approved change):
- **A.** Point the live forecast path at **B1** (the approved model), keeping V8 / market-blend as
  clearly-labeled experiments; or
- **B.** Keep `candidate.py` (V8) labeled experimental and excluded from runtime (status quo of its
  docstring/role), and formally register the market-anchored blend as an experiment, with B1 as the
  approved fallback of record.
Until that is approved, **B1 is the approved model of record.** No promotion may occur without a
paired-bootstrap improvement over B1 on the DEV folds.

## Promotion rule (for any future candidate, incl. V8 or a market model)
A candidate is promoted only if, on the DEV folds, its paired-bootstrap RPS (and log-loss) delta vs
B1 has a 95% CI excluding 0 in its favour, AND it does not regress the 2022 release gate, AND its
calibration is reported. Record the promotion here with commit hash + evaluation path.
