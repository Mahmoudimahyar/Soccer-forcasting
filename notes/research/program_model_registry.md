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

## Shadow-candidate status
**None.** No model meets the SHADOW-CANDIDATE bar (≥2 independent competition/time holdouts +
calibration + match-level bootstrap support + point-in-time collectable). See
`DURABLE_COLLECTOR_AND_SCHEDULER.md`. Promotion to runtime requires separate human approval + a
multi-tournament dataset.
