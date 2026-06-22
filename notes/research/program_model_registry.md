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
| In-play M2cal recalibrated | in-play | worse out-of-competition calibration | rejected |

## Shadow-candidate status (UPDATED 2026-06-21 — multi-competition unblocked on free tier)
**M2 (remaining-time Poisson) and M6 (market-anchored) = SHADOW-CANDIDATES** (research-only, NOT
runtime-approved). On leave-one-COMPETITION-out across **4 competitions / 4 confederations** (WC2022 +
Euro2024 + Copa2024 + AFCON2023-partial; 132 matches) both beat M1 on **4/4 held-out competitions**
with match-level bootstrap support (M2 dRPS −0.0165 CI [−0.025,−0.008]; M6 −0.0173 CI [−0.029,−0.006]);
M2 calibration slope 0.77, ECE 0.037. **Market ≈ Elo in-play** (M6 vs M2 CI includes 0). M5 also
passes; M2cal recalibration rejected. Criteria met: ≥2 (here 4) independent holdouts ✓, match-level
bootstrap ✓, point-in-time collectable ✓, separate from runtime ✓, calibration acceptable ✓.
**Still research-only; runtime promotion needs separate human approval.** More competitions
(AFCON completion, Nations League) fetchable on the free tier across daily-quota windows.
