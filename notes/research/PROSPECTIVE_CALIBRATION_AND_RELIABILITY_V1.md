# Prospective Calibration & Reliability V1

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

Observed draw rate = **0.265** on 34 fixtures. Calibration diagnostics only; no model's calibration was modified.

| model | ECE | draw cal slope | draw cal intercept | mean pred draw | obs draw |
|---|---|---|---|---|---|
| M1_B1 | 0.1352 | 1.479 | 0.904 | 0.211 | 0.265 |
| M2_market | 0.0826 | 2.721 | 2.273 | 0.220 | 0.265 |
| M3_75_25 | 0.1309 | 1.929 | 1.430 | 0.214 | 0.265 |
| M4_50_50 | 0.0783 | 2.342 | 1.894 | 0.216 | 0.265 |
| M5_25_75 | 0.0736 | 2.629 | 2.200 | 0.218 | 0.265 |

Draw-calibration slope/intercept are noisy logistic diagnostics at this n (~9 draws) and are reported for transparency only. All models slightly under-predict draws; reliability bins in `model_reliability_bins.csv`.
