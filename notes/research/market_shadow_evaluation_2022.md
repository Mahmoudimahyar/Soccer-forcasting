# 2022 WC Market Shadow Evaluation (READ-ONLY) — 2026-06-21

Shadow benchmark on the 2022 group stage (48/48 matches with aligned no-vig odds). **No model was
fitted to 2022; no blend weight was selected; nothing is promoted; `candidate.py` is untouched; B1
remains the sole approved runtime model. 2022 stays a release gate, not a selection set.**
Artifacts: `outputs/research/market_shadow_metrics_2022.csv`, `..._bootstrap_2022.csv`.

## Frozen models
M1 B1 (Elo r=0.4) · M2 market no-vig consensus · M3 equal blend (=50/50) ·
M4 predeclared fixed blends 75/25, 50/50, 25/75 (B1/market).

## Metrics (2022, lower better except where noted)
| model | RPS | log loss | draw Brier | draw cal err | worst-match LL | mean p(draw) |
|---|---|---|---|---|---|---|
| M1 B1 Elo | 0.2435 | 1.1217 | 0.1574 | 0.0429 | 4.10 | 0.229 |
| M2 market | **0.2244** | **1.0366** | 0.1545 | 0.0916 | 3.32 | 0.244 |
| M3 = 50/50 | 0.2313 | 1.0613 | 0.1552 | 0.0282 | 3.41 | 0.237 |
| M4 75/25 | 0.2367 | 1.0841 | 0.1561 | **0.0246** | 3.47 | 0.233 |
| M4 25/75 | 0.2272 | 1.0461 | 0.1547 | 0.0621 | 3.37 | 0.240 |
(actual draw rate 0.208.)

## Paired bootstrap vs B1 (2000 resamples; negative = better; significant if 95% CI excludes 0)
| model | dRPS | dRPS 95% CI | RPS sig? | dLogLoss | dLL 95% CI | LL sig? |
|---|---|---|---|---|---|---|
| M2 market | −0.0191 | [−0.046, +0.005] | no | −0.085 | [−0.206, +0.013] | no |
| M3 50/50 | −0.0121 | [−0.026, +0.001] | no | −0.060 | [−0.141, −0.002] | **yes** |
| M4 75/25 | −0.0067 | [−0.013, −0.0005] | **yes** | −0.038 | [−0.084, −0.003] | **yes** |
| M4 25/75 | −0.0162 | [−0.036, +0.002] | no | −0.076 | [−0.175, +0.004] | no |

## Reliability (draw probability)
- B1: bin[0.0,0.2) n=15 pred .15 obs .067 · bin[0.2,0.4) n=33 pred .265 obs .273 — well calibrated.
- Market: bin[0.0,0.2) n=8 pred .149 obs .000 · bin[0.2,0.4) n=40 pred .263 obs .250 — slightly
  over-confident on low-draw matches (worse draw ECE, 0.092 vs B1 0.043). Blends fix this (75/25 best).

## Conclusion (the only question asked)
**Does market information appear to contain incremental predictive signal beyond B1 in this dataset?
Yes — suggestively.** Adding market info to B1 produces **statistically significant log-loss
improvements** (M3/M4 CIs exclude 0) and the **75/25 blend significantly improves RPS** (CI excludes
0). Market-alone is directionally best on RPS/log-loss but its CI includes 0 (48 matches is
underpowered for RPS), and it is worse-calibrated on draws.

## Strict caveats (no action taken)
- This is **one tournament / a release gate**, not a development selection set. The significant LL
  effect on a single fold is **not sufficient** to promote any blend.
- **No blend weight is selected from 2022.** The 75/25 RPS result is reported, not chosen.
- A leakage-safe promotion would require the same effect on **pre-2022 development folds
  (2010/2014/2018)** — which needs timestamp-valid pre-2020 odds we do **not** have (see
  `data_requests/pending/historical_odds_dev_folds.yaml`). Until then, **no market model can clear
  the frozen promotion protocol**, and B1 stays approved.
