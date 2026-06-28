# International Event Lake — Match-Level Power Analysis

_research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible_

- Independent unit: **MATCH** (snapshot-clustered)
- Observed matches (M): 231  |  tournaments: 5  |  matches/tournament: 46.2
- Reference R0: `research.event_process.e2`  |  candidate template: `research.event_process.e7`
- Observed mean paired delta (e7 - e2): -0.00275  (sd 0.05933)
- R0 mean per-match RPS: 0.1415583980287633  |  candidate mean per-match RPS: 0.13880670595984546

## Current power at observed M (per absolute RPS gain)

| abs RPS gain | power @ M |
|---|---|
| 0.0005 | 0.040 |
| 0.0010 | 0.052 |
| 0.0020 | 0.100 |
| 0.0030 | 0.133 |
| 0.0050 | 0.280 |
| 0.0100 | 0.705 |

## Matches needed for target power

| abs RPS gain | 60% | 80% | 90% |
|---|---|---|---|
| 0.0005 | None | None | None |
| 0.0010 | None | None | None |
| 0.0020 | None | None | None |
| 0.0030 | 2000 | None | None |
| 0.0050 | 800 | 1200 | 2000 |
| 0.0100 | 200 | 500 | 500 |

## Tournaments needed for target power (at observed matches/tournament)

| abs RPS gain | 60% | 80% | 90% |
|---|---|---|---|
| 0.0005 | None | None | None |
| 0.0010 | None | None | None |
| 0.0020 | None | None | None |
| 0.0030 | 43.29 | None | None |
| 0.0050 | 17.32 | 25.97 | 43.29 |
| 0.0100 | 4.33 | 10.82 | 10.82 |

## Lever: more snapshots, SAME matches (clustering ceiling)
- gain 0.0010: power 0.058 -> 0.058 (delta +0.000) — adding snapshots to the same matches does not add power
- gain 0.0030: power 0.140 -> 0.140 (delta +0.000) — adding snapshots to the same matches does not add power

## Lever: coverage / imbalance (drop to 60% coverage floor)
- gain 0.0005: power 0.040 (M=231) -> 0.040 (M=139)
- gain 0.001: power 0.052 (M=231) -> 0.050 (M=139)
- gain 0.002: power 0.100 (M=231) -> 0.068 (M=139)
- gain 0.003: power 0.133 (M=231) -> 0.135 (M=139)
- gain 0.005: power 0.280 (M=231) -> 0.198 (M=139)
- gain 0.01: power 0.705 (M=231) -> 0.492 (M=139)

## Power-estimate uncertainty (independent RNG streams)
- gain 0.0010: mean 0.057 [0.048, 0.077] over 5 streams
- gain 0.0030: mean 0.135 [0.110, 0.175] over 5 streams
- gain 0.0050: mean 0.268 [0.215, 0.300] over 5 streams

_Deterministic; master_seed=20260628, n_outer=400, b_inner=400._

