# Nested In-Play Evaluation (Phase 5, 2026-06-22)

Proper **nested leave-one-competition-out** on StatsBomb men's senior international data — the clean
replacement for the earlier selection-contaminated 2026 ranking. **No 2026 match is used anywhere.**
Outer loop leaves one competition out; the inner loop selects the model using ONLY the remaining
training competitions; the outer competition is scored once with the inner-selected model.

Data: 6 modern men's international tournaments (AFCON2023, Copa2024, Euro2020, Euro2024, WC2018, WC2022),
**302 Elo-resolved matches / 5738 decision rows**. Data provided by StatsBomb (non-commercial research).

## Candidates (bounded, pre-specified)
M1, M2, M2temp, M2fit, M2fit_temp, M5, and M1 + each pre-registered xG family (+ all-xG).

## Per-fold inner selection
| outer held-out | selected model | inner RPS |
|---|---|---|
| AFCON2023 | **M5** | 0.1429 |
| Copa2024 | **M2** | 0.1525 |
| Euro2020 | **M2** | 0.1502 |
| Euro2024 | **M2** | 0.1477 |
| WC2018 | **M2** | 0.1445 |
| WC2022 | **M5** | 0.1434 |

**Plain M2 is selected in 4/6 folds; M5 in 2/6. M2temp, M2fit, M2fit_temp, and every xG variant are
NEVER selected.**

## Outer result (the honest number)
- Nested selected-model outer **RPS = 0.1487**.
- Reference (no selection): **M2 LOGO = 0.1474**, M1 LOGO = 0.1528.
- **Nested vs M1: dRPS −0.0042, CI [−0.0083, +0.0002] → not significant** (just misses).
- Note: the nested-selected RPS (0.1487) is **slightly worse than always using plain M2** (0.1474) —
  the inner selection occasionally picks M5 and adds noise. **A single transparent M2 is as good as or
  better than any selected combination here.**

## Calibration / RPS by state (selected model)
- by minute: 0–30 = 0.197 · 30–60 = 0.158 · 60–95 = 0.099 (later = easier, as expected).
- by score state: lead = 0.079 · level = 0.208 · trail = 0.100 (level mid-game is the hard regime).
- by card state: no_red = 0.149 · red = 0.145 (no degradation under red cards).

## Verdicts
- **Does M2fit_temp survive nested evaluation? NO** — it is never selected; plain M2 wins.
- **Does temperature scaling / fitted goal-rate help under clean evaluation? NO** — not selected.
- **Do the in-play models beat M1? Directionally yes, but NOT significant** on this international set
  (CI includes 0). The robust, defensible in-play model is **plain M2 (remaining-time Poisson)**.
- The earlier 2026 "M2fit_temp best" was a **selection-on-test artifact** (see
  `inplay_evaluation_reconciliation.md`).

See `inplay_xg_preregistered_results.md` and `inplay_model_selection_report.md`.
