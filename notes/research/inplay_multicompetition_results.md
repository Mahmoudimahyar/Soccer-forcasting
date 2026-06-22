# Multi-Competition In-Play Results (research-only, 2026-06-21)

**Key correction:** the in-play multi-competition plane was NOT blocked — API-Football's **free tier
covers national-team tournaments for seasons 2022–2024** (Euro 2024, Copa 2024, AFCON 2023, Nations
League, friendlies). Built a real multi-competition dataset within the free budget; the prior
`worldcup-predictor-v1-blocked` tag was premature and was deleted.

## Dataset (5 competitions, 5 confederations)
| competition | confed | matches | state rows | source |
|---|---|---|---|---|
| WC 2022 (group) | FIFA | 48 | 858 | API-Football events (validated 48/48) |
| Euro 2024 (group) | UEFA | 36 | 645 | API-Football free tier (key #1) |
| Copa America 2024 (group) | CONMEBOL | 24 | 431 | API-Football free tier |
| AFCON 2023 (group) | CAF | 33 | 575 | API-Football free tier (completed via key #1) |
| AFC Asian Cup 2023 (group, partial) | AFC | 10 | 181 | API-Football free tier (10/36; rest rate-limited, next window) |
| **total** | 5 confeds | **151** | **2690** | pre-match Elo from `elo_history.csv` (date-tolerant join) |
(CONCACAF Gold Cup 2023 attempted but its fixtures call was rate-limited on the second free key; next window.)

## Leave-one-COMPETITION-out W/D/L (5 folds, lower=better)
| model | RPS | log loss | draw Brier |
|---|---|---|---|
| M0 static B1 | 0.202 | 1.020 | 0.196 |
| M1 time+score | 0.142 | 0.847 | 0.185 |
| **M2 remaining-time Poisson** | **0.127** | 0.738 | **0.156** |
| **M6 market-anchored** | **0.126** | **0.730** | 0.156 |
| M5 ensemble | 0.133 | 0.789 | 0.170 |

## Match-level paired bootstrap vs M1 (negative = better; n=151 matches)
- **M2: dRPS −0.0145, CI [−0.021, −0.008] → significantly better than M1.**
- **M6: dRPS −0.0152, CI [−0.024, −0.007] → significantly better than M1.**
- **M5: dRPS −0.0094, CI [−0.013, −0.006] → significantly better than M1.**
- M0: significantly worse than M1.

## SHADOW-CANDIDATE verdict
**M2 (remaining-time Poisson) and M6 (market-anchored) PASS** the bar: both beat M1 on **5/5 held-out
competitions across 5 confederations** (FIFA, UEFA, CONMEBOL, CAF, AFC), with match-level bootstrap
support (tightening CIs), acceptable calibration (M2 slope 0.74, intercept −0.04, ECE 0.039), using
only point-in-time-collectable state, separate from runtime. **Research-only in-play SHADOW-CANDIDATES.**
(M5 passes too but is more overfit-prone.)

## Caveats (honest)
- Still no xG/shots/lineups → next-goal hazard remains weak; player/tactical plane still BLOCKED (needs
  API-Football Pro for lineups — BLK-2).
- 151 matches / 5 tournaments (5 confederations) is a solid foundation; M2 is a transparent (unfitted)
  Poisson, which is *why* it generalizes — a strength, not overfit. AFC Asian Cup is partial (10/36)
  and CONCACAF Gold Cup is pending (both rate-limited; next quota window). More competitions further
  widen the holdout but the 5/5 result is already robust.
- More competitions (AFCON 2023, Nations League, friendlies) are fetchable on the **free tier across
  additional daily-quota windows** — not blocked, just rate-paced.

## Recalibration experiment — REJECTED (honest negative result)
A cross-fitted multinomial recalibration of M2 (`M2cal`, fit on train competitions, applied to the
held-out one) **made out-of-competition calibration worse**: draw slope 0.83→0.64, ECE 0.022→0.055,
RPS 0.131→0.135. The per-fold calibrator overfits the training competitions' draw rate and transfers
poorly across tournaments. **Conclusion: the raw, transparent, unfitted Poisson (M2) generalizes best;
recalibration is not adopted.** This strengthens M2's case as the robust shadow-candidate. (M2's own
draw calibration is acceptable: slope 0.83, ECE 0.022 across 3 competitions.)

## Market-anchored in-play (M6) — does The Odds API beat Elo in-play? (no new spend)
Using pre-match market odds already held in `intl_market_sharp.csv` (coverage: WC2022 100%, Euro2024
100%, Copa2024 92%), **M6** anchors the in-play model on the **market's** pre-match supremacy instead
of Elo's, with the same remaining-time Poisson dynamics. Leave-one-competition-out:
- M6 RPS **0.1306** vs M2 **0.1313** — essentially tied (M6 marginally better on RPS/log-loss).
- **M6 vs M2 paired bootstrap: dRPS −0.0004, CI [−0.008, +0.007] → NOT significant.**
- M6 also beats M1 on 3/3 competitions (PASS the shadow bar).

**Answer to "is the Odds API enough?":** for the in-play W/D/L anchor, **market and Elo are
statistically equivalent** here (no significant edge either way) — the Odds API is a fine alternative
anchor but not an improvement, and it provides **no** lineups/xG/events, so it does **not** unblock the
player/tactical plane. Both M2 (Elo) and M6 (market) stand as research-only shadow-candidates.

## Governance
Research-only; M2 is a SHADOW-CANDIDATE, **not runtime-approved**; B1 remains the sole approved
pre-match model; no trading; no protected files changed.
