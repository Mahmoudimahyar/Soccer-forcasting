> [!WARNING]
> **SUPERSEDED / CORRECTED (banner added 2026-09-20; original text kept unedited below).**
>
> **Artifacts of a bug:** the "candidate V8" row of the scorecard (RPS 0.221 / log-loss 1.082 / draw-cal 0.022;
> later re-run as 0.225 / 1.092 / 0.004) and every conclusion drawn from it — points 1, 2 and 4 and the
> "Implication" section. In `scripts/prequential_2026.py` the candidate's one-row test frame had all-object
> dtype, so every feature was zero-filled and the candidate produced near-constant forecasts.
>
> **Corrected (bug fixed 2026-09-20), same 33 matches:** V8 scores RPS 0.173 / log-loss 0.948 / draw-cal 0.175
> against B1 0.174 / 0.958 / 0.178 — a tie. Neither "worse than Elo" nor "better draw calibration" holds. B1's
> figures were never affected.
>
> See [ERRATA E1](../../docs/ERRATA.md), [`scripts/prequential_2026.py`](../../scripts/prequential_2026.py) and the
> [glossary](../../docs/GLOSSARY.md).

# Prequential Out-of-Sample Scorecard — 2026 (live test)

`scripts/prequential_2026.py`. For each FINISHED 2026 group match in chronological order, every
model is trained only on group matches that kicked off strictly before it (history + earlier
2026) and then scored against the actual result. No post-kickoff information is used. This is
the genuine live out-of-sample test (protocol section 4D). 33 finished matches so far (24 MD1,
9 MD2). Re-run as more matches finish (re-fetch football-data first).

## Scorecard (lower is better except acc)
| model | RPS | LogLoss | draw-Brier | draw-cal | acc | composite |
|---|---|---|---|---|---|---|
| candidate V8 (Elo-blend logit) | 0.221 | 1.082 | 0.213 | **0.022** | 0.55 | 0.405 |
| **B1 ternary-Elo** | **0.174** | **0.958** | 0.232 | 0.178 | 0.55 | **0.382** |
| B0 historical prior | 0.215 | 1.072 | 0.215 | 0.088 | 0.55 | 0.401 |
| uniform 1/3 | 0.227 | 1.099 | — | — | — | — |

(composite = 0.40·RPS + 0.25·LogLoss + 0.20·draw-Brier + 0.15·draw-cal)

## What this says (honestly)
1. **Plain Elo is the best model out-of-sample on 2026** — on RPS, log loss, and even the full
   composite. The accepted candidate (selected because it beat Elo on the 2018/2022 folds) does
   NOT transfer that advantage to 2026.
2. **The candidate's value is draw calibration, not sharpness.** Its draw-calibration error is
   0.022 (vs Elo's 0.178) and its mean predicted draw rate (0.325) almost exactly matches the
   actual 0.303. The 50% Elo blend + logit deliberately softens favorites, which helps draws but
   costs RPS/log-loss when favorites win.
3. **2026 has been hard to predict.** Even the best model's RPS (0.174) is not far below uniform
   (0.227); MD1 produced several level/upset results. Small sample (33) — treat as provisional.
4. This is the locked-holdout doing its job: it reveals that selecting on 2018/2022 draw patterns
   produced a model that is well-calibrated on draws but not sharper than Elo on the live data.

## Implication (reported, not acted on — no tuning to the holdout)
For the **2026 forecasts specifically**, plain Elo (B1) has scored best so far; the calibrated
candidate is preferable only if draw calibration is the priority. A defensible production choice
is to lean more on Elo (higher blend weight) — but that change must be justified on the *fixed
selection folds*, not on this 2026 scorecard, to avoid tuning to the holdout. Logged as the
cycle-3 question.

## vs the market
Where live odds exist (upcoming matches), the market remains the benchmark; this scorecard
covers already-finished matches for which we have no stored pre-match odds. As upcoming matches
finish, extend the harness to also score the saved market consensus and the model's edges
(`forecast_2026_market_anchored.csv`) — that is the true model-vs-market test.
