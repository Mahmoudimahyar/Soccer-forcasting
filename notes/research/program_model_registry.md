# Program Model Registry (V1)

Single list of every model and its status. Authoritative approval source remains
`configs/approved_models.yaml` + `approved_model_registry.md`.

## Approved (runtime)
| model | role | status | evidence |
|---|---|---|---|
| **B1 ternary-Elo (r=0.4)** | pre-match 1X2 | **APPROVED** (sole) | tier-2 gate; reconciliation; `approved-b1-runtime` |

## Experimental / research-only (NOT runtime; `research_only=true, not_runtime_approved=true`)
| model | plane | best evidence | verdict |
|---|---|---|---|
| V8 (logit + 0.85 Elo blend) | pre-match | worse than B1 on 2026 prequential | not promoted |
| Scoreline Poisson / Dixon-Coles | pre-match scoreline | dev 0.358/0.357 > B1 0.355 | not promoted (adds scoreline outputs only) |
| Market blends M2–M5 | pre-match | 2022 shadow: LL gain, RPS underpowered | shadow-only; dev-fold odds blocked |
| In-play M0 static B1 | in-play | control | baseline |
| In-play M1 time+score | in-play | RPS 0.175 | baseline |
| In-play M2 remaining Poisson | in-play | RPS 0.155 (best), CI vs M1 incl 0 | research leader (not shadow-ready) |
| In-play M3 goal hazard | next-goal | fails vs base rate | rejected (sparse features) |
| In-play M4 competing-risk | next-goal team | LL 1.03 < base 1.08 | weak signal |
| In-play M5 ensemble | in-play | beats M1 with match-level significance | research leader |
| In-play M6 market-anchored | in-play | ≈ M2 (dRPS −0.0004, CI incl 0); beats M1 3/3 | market ≈ Elo anchor (no sig. edge); research-only |
| In-play M2cal recalibrated | in-play | multinomial recal; OK but bested by M2temp | superseded by M2temp |
| In-play M2temp (temp-scaled M2) | in-play | 6-comp LOGO: log-loss 0.737, draw slope 1.02, RPS 0.131 | strong (research-only) |
| **In-play M2fit_temp (fitted anchor + temp)** | in-play | **6-comp LOGO: best log-loss 0.7358, best draw-Brier 0.1582, RPS 0.1307; best 2026-OOS RPS 0.1429; beats M1 sig** | **BEST in-play model (research-only)** |
| In-play live-xG (StatsBomb) | in-play | 2-comp LOGO (WC2022+Copa2024, 68 matches): no sig W/D/L gain; cumulative xG hurts next-goal | NEGATIVE (research-only) |
| In-play M2fit (data-fitted goal-rate) | in-play | base 1.35→1.14, k 0.20→0.15 from actual goals; RPS 0.1306, beats M1 dRPS −0.013 | improves M2 anchor (research-only) |

## NESTED CV CORRECTION (2026-06-22, sprint evaluation-reset-event-expansion)
Proper nested leave-one-competition-out on 302 StatsBomb men's international matches (NO 2026, no
test-peeking): inner selection picks **plain M2 (4/6 folds)** / M5 (2/6); **M2temp, M2fit, M2fit_temp,
and all xG variants are NEVER selected**. Nested-selected outer RPS 0.1487 vs plain **M2 LOGO 0.1474**
vs M1 0.1528; nested-vs-M1 dRPS −0.0042 CI [−0.0083,+0.0002] (ns). **M2fit_temp does NOT survive**; the
earlier "best" was selection-on-test. **Reference in-play model = M2.** xG adds nothing (all 6
pre-registered families ns). See `inplay_nested_evaluation.md`, `inplay_model_selection_report.md`,
`inplay_xg_preregistered_results.md`. B1 remains the sole runtime model.

## OUT-OF-SAMPLE on the LIVE 2026 World Cup (UPDATED 2026-06-22 — Pro plan; SUPERSEDED by nested CV above for model RANKING)
Decisive test: fit on 5 pre-2026 competitions, predict 30 finished 2026 matches (held out, never tuned).
- **In-play >> static B1: M1 vs M0 dRPS −0.0447, CI [−0.084,−0.005] → SIGNIFICANT** (RPS 0.190→0.146,
  ~24%). The in-play layer is the program's first improvement **validated out-of-sample on the actual
  target event**.
- Among in-play models, differences are **not significant at n=30** (M5/M2cal/M2 vs M1 all ns).
- Calibration (draw) on 2026: **M2cal ECE 0.057 and M5 0.059 are best; transparent M2 is worst (0.093)**
  — recalibration/ensembling generalize better OOS than the transparent Poisson. See
  `inplay_2026_holdout.md`. Nothing promoted; B1 remains sole runtime model.
- **Improvement shipped: `TemperatureScaled` (1 dof, fit on train comps only).** Full 6-competition
  LOGO: **M2temp = best log-loss (0.737), near-ideal draw calibration (slope 1.02, ECE 0.022), RPS
  0.131 (best-tier), beats M1 dRPS −0.013 CI[−0.019,−0.007]**. Best-calibrated in-play model; transparent
  base + single temperature. Research-only; B1 still sole runtime.

## Shadow-candidate status (UPDATED 2026-06-21 — multi-competition unblocked on free tier)
**M2 (remaining-time Poisson) and M6 (market-anchored) = SHADOW-CANDIDATES** (research-only, NOT
runtime-approved). On leave-one-COMPETITION-out across **5 competitions / 5 confederations** (WC2022 +
Euro2024 + Copa2024 + AFCON2023 + AsianCup2023-partial; 151 matches) both beat M1 on **5/5 held-out
competitions** with match-level bootstrap support (M2 dRPS −0.0145 CI [−0.021,−0.008]; M6 −0.0152 CI
[−0.024,−0.007]); M2 calibration slope 0.74, ECE 0.039. **Market ≈ Elo in-play** (M6 vs M2 CI includes 0). M5 also
passes; M2cal recalibration rejected. Criteria met: ≥2 (here 4) independent holdouts ✓, match-level
bootstrap ✓, point-in-time collectable ✓, separate from runtime ✓, calibration acceptable ✓.
**Still research-only; runtime promotion needs separate human approval.** More competitions
(AFCON completion, Nations League) fetchable on the free tier across daily-quota windows.
