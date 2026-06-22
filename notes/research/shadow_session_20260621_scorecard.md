# Shadow Session 2026-06-21 — Scorecard

**SINGLE MATCH (n=1). DESCRIPTIVE ONLY. NO statistical significance. Not model selection.**
Source CSV: `outputs/live_shadow/session_20260621T182402Z/scorecard.csv`.

## Scorable set
Only **Belgium–Iran** (match_id `2026_G_0621_BelIra`, KO 19:00Z) finished within the session
(**0-0, Draw**; result football-data.org, verified 21:14:17Z). Uruguay–Cape Verde finished after the
deadline → not scorable. Scoring rule enforced: `snapshot_ts ≤ prediction_ts < kickoff`.

## Belgium–Iran result = DRAW (0-0). Frozen M1–M5 (lower = better)
| model | snapshot | p(draw) | RPS | log loss | draw Brier |
|---|---|---|---|---|---|
| **M1 B1** | final_pre_kickoff | 0.273 | **0.155** | **1.299** | **0.529** |
| M3 75/25 | final_pre_kickoff | 0.255 | 0.172 | 1.365 | 0.555 |
| M4 50/50 | final_pre_kickoff | 0.238 | 0.192 | 1.436 | 0.581 |
| M5 25/75 | final_pre_kickoff | 0.220 | 0.215 | 1.513 | 0.608 |
| M2 market | final_pre_kickoff | 0.203 | 0.239 | 1.596 | 0.636 |

(T-15 and the pre-supervisor manual snapshot give essentially identical numbers — B1 is stable and
the odds barely moved across 18:06→18:55Z.)

## Descriptive observation (NOT a conclusion)
On this one match — a **0-0 draw that upset a market-implied Belgium favorite** (market p(Belgium win)
≈ 0.68) — **B1 ranked best and the market worst**, with the blends monotonically ordered by their B1
weight. This is the *opposite* directional result from the 2022 gate study (where market blends helped
on average). **Both are individually uninformative about the truth:** 2022 was 48 matches (still a
release gate, not selection) and this is **a single match**. One game cannot confirm or refute market
value; it only starts the prospective ledger.

## Governance
No model promoted; B1 remains the sole approved runtime model; M2–M5 shadow; this scorecard is not
used to select a blend weight or modify `candidate.py`. Accumulate many more finished matches before
any descriptive trend is even worth discussing, and never from a single session.
