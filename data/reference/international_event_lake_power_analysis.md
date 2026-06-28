# International Event Lake — Match-Level Power Analysis

_research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible_

- Independent unit: **MATCH** (snapshot-clustered)
- Observed matches (M): 56  |  tournaments: 5  |  matches/tournament: 11.2
- Reference R0: `research.event_process.e2`  |  candidate template: `research.event_process.e7`
- Observed mean paired delta (e7 - e2): 0.02190  (sd 0.10000)
- R0 mean per-match RPS: 0.14180178353219738  |  candidate mean per-match RPS: 0.16370586931875897

## Current power at observed M (per absolute RPS gain)

| abs RPS gain | power @ M |
|---|---|
| 0.0005 | 0.033 |
| 0.0010 | 0.027 |
| 0.0020 | 0.047 |
| 0.0030 | 0.047 |
| 0.0050 | 0.093 |
| 0.0100 | 0.127 |

## Matches needed for target power

| abs RPS gain | 60% | 80% | 90% |
|---|---|---|---|
| 0.0005 | None | None | None |
| 0.0010 | None | None | None |
| 0.0020 | None | None | None |
| 0.0030 | None | None | None |
| 0.0050 | 2000 | None | None |
| 0.0100 | 500 | 800 | 1200 |

## Tournaments needed for target power (at observed matches/tournament)

| abs RPS gain | 60% | 80% | 90% |
|---|---|---|---|
| 0.0005 | None | None | None |
| 0.0010 | None | None | None |
| 0.0020 | None | None | None |
| 0.0030 | None | None | None |
| 0.0050 | 178.57 | None | None |
| 0.0100 | 44.64 | 71.43 | 107.14 |

## Lever: more snapshots, SAME matches (clustering ceiling)
- gain 0.0010: power 0.043 -> 0.043 (delta +0.000) — adding snapshots to the same matches does not add power
- gain 0.0030: power 0.060 -> 0.060 (delta +0.000) — adding snapshots to the same matches does not add power

## Lever: coverage / imbalance (drop to 60% coverage floor)
- gain 0.0005: power 0.033 (M=56) -> 0.053 (M=34)
- gain 0.001: power 0.027 (M=56) -> 0.030 (M=34)
- gain 0.002: power 0.047 (M=56) -> 0.030 (M=34)
- gain 0.003: power 0.047 (M=56) -> 0.060 (M=34)
- gain 0.005: power 0.093 (M=56) -> 0.093 (M=34)
- gain 0.01: power 0.127 (M=56) -> 0.107 (M=34)

## Power-estimate uncertainty (independent RNG streams)
- gain 0.0010: mean 0.037 [0.030, 0.047] over 5 streams
- gain 0.0030: mean 0.049 [0.043, 0.060] over 5 streams
- gain 0.0050: mean 0.067 [0.050, 0.077] over 5 streams

_Deterministic; master_seed=20260628, n_outer=300, b_inner=300._

