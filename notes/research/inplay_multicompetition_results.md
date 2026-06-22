# Multi-Competition In-Play Results (research-only, 2026-06-21)

**Key correction:** the in-play multi-competition plane was NOT blocked — API-Football's **free tier
covers national-team tournaments for seasons 2022–2024** (Euro 2024, Copa 2024, AFCON 2023, Nations
League, friendlies). Built a real multi-competition dataset within the free budget; the prior
`worldcup-predictor-v1-blocked` tag was premature and was deleted.

## Dataset (3 competitions)
| competition | matches | state rows | source |
|---|---|---|---|
| WC 2022 (group) | 48 | 858 | API-Football events (validated 48/48) |
| Euro 2024 (group) | 36 | 645 | API-Football free tier |
| Copa America 2024 (group) | 24 | 431 | API-Football free tier |
| **total** | **108** | **1934** | pre-match Elo from `elo_history.csv` (date-tolerant join) |

## Leave-one-COMPETITION-out W/D/L (lower=better)
| model | RPS | log loss | draw Brier |
|---|---|---|---|
| M0 static B1 | 0.208 | 1.021 | 0.179 |
| M1 time+score | 0.145 | 0.876 | 0.167 |
| **M2 remaining-time Poisson** | **0.131** | **0.737** | **0.144** |
| M5 ensemble | 0.136 | 0.775 | 0.156 |

## Match-level paired bootstrap vs M1 (negative = better; n=108 matches)
- **M2: dRPS −0.0143, CI [−0.024, −0.004] → significantly better than M1.**
- **M5: dRPS −0.0090, CI [−0.014, −0.004] → significantly better than M1.**
- M0: significantly worse than M1.

## SHADOW-CANDIDATE verdict
**M2 (remaining-time Poisson) PASSES** the bar: beats M1 on **3/3 held-out competitions**, match-level
bootstrap support, draw ECE 0.026 (calibration slope 0.76 = mild overconfidence to recalibrate),
uses only point-in-time-collectable state (score/minute/cards), separate from runtime. M5 also passes
but is more overfit-prone (fitted calibrator). **M2 is the research-only in-play SHADOW-CANDIDATE.**

## Caveats (honest)
- Still no xG/shots/lineups → next-goal hazard remains weak; player/tactical plane still BLOCKED (needs
  API-Football Pro for lineups — BLK-2).
- 108 matches / 3 tournaments is a real foundation but not large; M2 is a transparent (unfitted)
  Poisson, which is *why* it generalizes — that is a strength, not overfit. Recalibrating its draw
  slope is the obvious next improvement.
- More competitions (AFCON 2023, Nations League, friendlies) are fetchable on the **free tier across
  additional daily-quota windows** — not blocked, just rate-paced.

## Governance
Research-only; M2 is a SHADOW-CANDIDATE, **not runtime-approved**; B1 remains the sole approved
pre-match model; no trading; no protected files changed.
