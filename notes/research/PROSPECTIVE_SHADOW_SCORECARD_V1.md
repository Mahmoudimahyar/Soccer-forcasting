# Prospective Shadow Scorecard V1

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

Primary one-snapshot-per-fixture benchmark on **34** completed 2026 WC group fixtures — **sample-size tier C_exploratory**. Match-level bootstrap (5000). Read-only; nothing promoted.

| model | RPS [95% CI] | log-loss [95% CI] | draw-Brier [95% CI] |
|---|---|---|---|
| M1_B1 | 0.1304 [0.0891, 0.1771] | 0.7754 [0.5857, 0.9860] | 0.1833 [0.1059, 0.2693] |
| M2_market | 0.1360 [0.0982, 0.1770] | 0.7740 [0.6070, 0.9521] | 0.1765 [0.1026, 0.2549] |
| M3_75_25 | 0.1304 [0.0909, 0.1762] | 0.7712 [0.5874, 0.9733] | 0.1812 [0.1076, 0.2639] |
| M4_50_50 | 0.1314 [0.0937, 0.1742] | 0.7697 [0.5943, 0.9596] | 0.1793 [0.1074, 0.2611] |
| M5_25_75 | 0.1333 [0.0945, 0.1756] | 0.7707 [0.6000, 0.9543] | 0.1778 [0.1056, 0.2611] |

## Paired fixture-level deltas (negative ⇒ row model better than reference)
| reference | model | metric | mean Δ [95% CI] | CI excludes 0 |
|---|---|---|---|---|
| M1_B1 | M2_market | rps | 0.0057 [-0.0118, 0.0226] | no |
| M1_B1 | M2_market | log_loss | -0.0015 [-0.0715, 0.0635] | no |
| M1_B1 | M2_market | draw_brier | -0.0068 [-0.0233, 0.0074] | no |
| M1_B1 | M3_75_25 | rps | 0.0001 [-0.0044, 0.0042] | no |
| M1_B1 | M3_75_25 | log_loss | -0.0042 [-0.0235, 0.0129] | no |
| M1_B1 | M3_75_25 | draw_brier | -0.0021 [-0.0063, 0.0016] | no |
| M1_B1 | M4_50_50 | rps | 0.0011 [-0.0080, 0.0094] | no |
| M1_B1 | M4_50_50 | log_loss | -0.0057 [-0.0416, 0.0274] | no |
| M1_B1 | M4_50_50 | draw_brier | -0.0039 [-0.0124, 0.0036] | no |
| M1_B1 | M5_25_75 | rps | 0.0029 [-0.0100, 0.0159] | no |
| M1_B1 | M5_25_75 | log_loss | -0.0047 [-0.0573, 0.0441] | no |
| M1_B1 | M5_25_75 | draw_brier | -0.0055 [-0.0180, 0.0059] | no |
| M2_market | M1_B1 | rps | -0.0057 [-0.0222, 0.0120] | no |
| M2_market | M1_B1 | log_loss | 0.0015 [-0.0622, 0.0729] | no |
| M2_market | M1_B1 | draw_brier | 0.0068 [-0.0080, 0.0226] | no |
| M2_market | M3_75_25 | rps | -0.0056 [-0.0189, 0.0073] | no |
| M2_market | M3_75_25 | log_loss | -0.0028 [-0.0495, 0.0470] | no |
| M2_market | M3_75_25 | draw_brier | 0.0047 [-0.0063, 0.0171] | no |
| M2_market | M4_50_50 | rps | -0.0046 [-0.0132, 0.0041] | no |
| M2_market | M4_50_50 | log_loss | -0.0043 [-0.0356, 0.0289] | no |
| M2_market | M4_50_50 | draw_brier | 0.0029 [-0.0044, 0.0109] | no |
| M2_market | M5_25_75 | rps | -0.0028 [-0.0073, 0.0016] | no |
| M2_market | M5_25_75 | log_loss | -0.0033 [-0.0185, 0.0126] | no |
| M2_market | M5_25_75 | draw_brier | 0.0013 [-0.0023, 0.0051] | no |

At tier C_exploratory no paired delta vs **both** B1 and the market excludes zero; differences are within sampling noise. **No model is ranked or promoted.**
