# Pre-registered xG Feature Results (Phase 5, 2026-06-22)

The six xG feature families were **fixed before testing** (`src/wcdrawlab/research/xg_features.py`,
`FAMILIES`). No additional variants were tried after seeing results. Evaluated by adding each family to
the M1 in-play logit and scoring on **6-competition leave-one-competition-out** (302 men's international
matches; StatsBomb). Match-level paired bootstrap vs the M1 baseline (RPS 0.1528).

| family | features | RPS | dRPS vs M1 | 95% CI | verdict |
|---|---|---|---|---|---|
| f1 xG-before | xg_diff_before | 0.1534 | +0.0006 | [−0.001, +0.002] | ns |
| f2 rolling-5 | roll5_xg_diff | 0.1529 | +0.0001 | [−0.000, +0.000] | ns |
| f3 rolling-10 | roll10_xg_diff | 0.1529 | +0.0001 | [−0.000, +0.000] | ns |
| f4 shot-count | shotcount5/10_diff | 0.1529 | +0.0001 | [−0.000, +0.000] | ns |
| f5 time-since-shot | tsl_shot | 0.1529 | +0.0001 | [−0.000, +0.000] | ns |
| f6 time-since-major | tsl_major | 0.1524 | −0.0004 | [−0.001, +0.001] | ns |
| all xG | all 7 cols | 0.1531 | +0.0002 | [−0.001, +0.002] | ns |

## Conclusion
**No pre-registered xG family improves the in-play W/D/L forecast** on men's international data; every CI
includes zero, and under nested selection (Phase 5) no xG variant is ever chosen. This supersedes the
earlier underpowered 2-competition xG test with a properly-powered 6-competition LOGO and the same
verdict: **xG, as derivable here, does not beat score + time + Elo for in-play 1X2.**

(Next-goal is the use case where xG is theoretically strongest, but that model class is **data-blocked**
— only ~333 men's international matches exist in StatsBomb; see
`player_card_substitution_readiness.md`. A club-auxiliary next-goal study is possible but the club data
lacks an Elo anchor — see the transfer note in the completion report.)
