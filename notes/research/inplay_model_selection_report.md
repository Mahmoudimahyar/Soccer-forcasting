# In-Play Model Selection Report (Phase 5, 2026-06-22)

## Recommended in-play model (research-only): **M2 — remaining-time Poisson**
Under nested leave-one-competition-out (no test-set peeking) on 302 men's international matches, plain
**M2** is the robust choice: selected in 4/6 outer folds, and its straight LOGO RPS (0.1474) is as good
as or better than any selected combination (nested-selected 0.1487) and clearly better than M1 (0.1528).
M2 is transparent (no fitted parameters), so it generalises across competitions and confederations.

## Models considered and their honest standing
| model | nested selection | verdict |
|---|---|---|
| **M2** remaining-Poisson | selected 4/6 | **recommended (research-only)** |
| M5 ensemble | selected 2/6 | viable but adds variance; no net gain |
| M1 time+score | never | weaker baseline (RPS 0.1528) |
| M2temp (temperature) | never | **not justified** under clean evaluation |
| M2fit (fitted goal-rate) | never | **not justified** under clean evaluation |
| M2fit_temp | never | **does NOT survive**; earlier "best" was selection-on-test |
| M1 + any xG family | never | no value (all ns; see preregistered results) |

## Why the earlier "M2fit_temp is best" was wrong
M2fit was built and M2fit_temp crowned after repeatedly viewing 2026 results — selection on the test
set. Under nested CV that never sees the held-out competition during selection, those enhancements add
nothing and are never picked. The honest conclusion is a **downgrade**: the only robust in-play claim is
that **M2 modestly improves over M1 (not significant here) and massively over static B1**, and that
**calibration tooling (temperature) and fitted/xG features are not warranted by the evidence**.

## What this means for the frozen prospective model
The Phase 2 freeze used `m2fit_temp` (the then-current candidate). Given this Phase 5 finding, the
**prospective protocol should be interpreted as a frozen *candidate*, not a validated best model**;
the cleaner scientific baseline for future 2026 scoring is plain M2. The freeze remains valid as an
immutable record (it predates this result); a future freeze may adopt M2. Either way: **research-only,
B1 remains the sole runtime model.**

## Decision
- Adopt **M2** as the reference research in-play model.
- Retire M2temp / M2fit / M2fit_temp / xG variants from "improvement" status to "evaluated, not
  justified" (kept in code as research artifacts, relabelled in the registry).
- In-play vs static-B1 remains the one robust, sizeable, validated gain.
