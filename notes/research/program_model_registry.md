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
| In-play M5 ensemble | in-play | beats M1 with match-level significance | research leader (not shadow-ready) |

## Shadow-candidate status (UPDATED 2026-06-21 — multi-competition unblocked on free tier)
**M2 (remaining-time Poisson) = SHADOW-CANDIDATE** (research-only, NOT runtime-approved). On
leave-one-COMPETITION-out across **WC2022 + Euro2024** it beats M1 (time+score) on **both** held-out
competitions with match-level bootstrap support (dRPS −0.016, CI [−0.028, −0.003]); draw ECE 0.026
(calibration slope 0.76 = mild overconfidence to recalibrate). M5 also passes the 2-holdout bar but is
more overfit-prone. Criteria met: ≥2 independent holdouts ✓, match-level bootstrap ✓, point-in-time
collectable ✓, separate from runtime ✓; calibration acceptable (improve slope). **Still research-only;
runtime promotion needs separate human approval + more competitions** (Copa/AFCON/NL fetchable on the
free tier across days). See `inplay_multicompetition_results.md`, `DURABLE_COLLECTOR_AND_SCHEDULER.md`.
