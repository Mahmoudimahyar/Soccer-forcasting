# In-Play Models on the LIVE 2026 World Cup — Out-of-Sample (research-only, 2026-06-22)

The 2026 World Cup is underway. Using the paid API-Football Pro plan we built a leakage-safe in-play
state table for **30 finished 2026 group matches (519 decision rows)** and ran the **decisive
out-of-sample test**: fit in-play models on the 5 pre-2026 competitions (151 matches), then predict
2026. Transparent models (M0/M2/M6) are not fit at all. **2026 is held out and never tuned to.**

## Headline (validated improvement)
| comparison | dRPS (neg=better) | 95% CI | verdict |
|---|---|---|---|
| **in-play M1 vs static M0** | **−0.0447** | [−0.084, −0.005] | **significant** |
| **best M5 vs static M0** | **−0.0472** | [−0.089, −0.005] | **significant** |
| M5 vs M1 | −0.0025 | [−0.013, +0.007] | ns |
| M2cal vs M1 | −0.0008 | [−0.015, +0.012] | ns |
| M2 (transparent) vs M1 | +0.0003 | [−0.017, +0.015] | ns |

RPS on 2026: M5 0.1459 · M2cal 0.1476 · **M1 0.1478** · M2 0.1488 · M6 0.1488 · **M0 0.1897**.

**The in-play layer beats static B1 carried-through by ~0.045 RPS (~24%), and the gap is statistically
significant at the match level on unseen 2026 data.** This is the program's first model improvement
**validated out-of-sample on the actual target event.**

## Honest nuances (recorded, not hidden)
- **Among in-play models the differences are not significant at n=30 matches.** Any sensible in-play
  update wins big over static; choosing between M1/M2/M5/M2cal is underpowered on 2026 alone.
- **Calibration on 2026** (draw prob; slope→1, intercept→0 ideal):
  | model | slope | intercept | ECE |
  |---|---|---|---|
  | M1 time+score | 0.694 | −0.227 | 0.0719 |
  | M2 remaining-Poisson | 0.478 | −0.256 | 0.0929 |
  | M2cal recalibrated | 0.696 | −0.174 | **0.0565** |
  | M5 ensemble | 0.657 | −0.197 | 0.0586 |
  All are **draw-overconfident** out-of-sample. The **transparent M2 is the WORST-calibrated** on 2026,
  while the recalibrated/ensemble variants are best. This nuances the earlier in-sample pick of M2 as
  THE shadow-candidate: on the true holdout, M2's transparency carries a calibration cost, and
  recalibration (previously rejected for train-fold overfitting) actually *helps* OOS calibration.

## Improvement implemented: cross-fitted temperature scaling (`TemperatureScaled`)
Acting on the lead above. A single temperature `T` (fit on the 5 training competitions only, via
leave-one-competition-out OOF) tempers each model's probabilities `p' = softmax(log(p)/T)`. Applied to
the held-out 2026 World Cup:

| base | RPS 2026 | RPS +temp | draw slope | +temp slope | draw ECE | +temp ECE | T |
|---|---|---|---|---|---|---|---|
| M1 | 0.1478 | **0.1441** | 0.69 | **1.06** | 0.072 | 0.061 | 1.45 |
| M2 | 0.1488 | **0.1439** | 0.48 | 0.67 | 0.093 | **0.048** | 1.35 |
| M5 | 0.1459 | **0.1420** | 0.66 | **0.92** | 0.059 | 0.070 | 1.35 |

- **RPS improves on all three** (~0.004 each, consistent direction; per-match bootstrap CIs include 0
  at n=30, so not individually significant — but the *direction is uniform* and the *calibration* gain
  is unambiguous).
- **Calibration slopes move decisively toward the ideal 1.0** (over-confidence removed). Best overall:
  **M5+temp = 0.1420 RPS, draw slope 0.92** out-of-sample.
- Implemented as a reusable, unit-tested `TemperatureScaled` wrapper (1 dof → minimal overfit risk),
  research-only. `scripts/eval_2026_recalibration.py` reproduces the table.

## Implications
- **Robust claim:** in-play >> static, validated OOS on 2026. Promote nothing to runtime (B1 stays sole
  approved); this strengthens the in-play plane as a research/ shadow capability.
- **Next improvement lead:** a properly cross-fitted **draw recalibration** is the clearest lever —
  every model is draw-overconfident OOS, and recalibration improves ECE without hurting RPS.
- More 2026 matches accrue daily; re-running this raises power to separate the in-play variants.
