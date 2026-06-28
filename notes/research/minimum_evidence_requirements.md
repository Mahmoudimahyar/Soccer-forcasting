# Minimum evidence requirements for an in-play residual-correction claim

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Source: `data/reference/minimum_evidence_requirements.json`, derived from the match-level power
curves in `data/reference/match_level_power_analysis.json` (run `evp_20260627_power1`).

## Premise

- **Reference:** `research.residual.w2_reference_r0` (parameter-free W2 remaining-time Poisson),
  pooled LOCO RPS **0.14906**.
- **Current evidence:** 58 independent international matches, 7376 snapshots, 5 tournaments.
  No candidate beat the reference; best candidate `selective_correction_r4` was 0.0049 RPS *worse*.
- **Independent unit:** the international **match** (all snapshots of a match are one cluster).
- **Observed match-level paired-delta sd vs reference:** 0.0199.

## Minimum independent international matches by effect size (80% power)

| Abs RPS improvement | ~% of reference | Power @ 58 | Matches @ 80% | Tournaments @ 80% | Verdict |
|---|---|---|---|---|---|
| 0.0005 | 0.3% | 0.10 | not reachable | >250 | undetectable at realistic volume |
| 0.0010 | 0.7% | 0.14 | not reachable | >170 (for 60%) | practically undetectable |
| 0.0020 | 1.3% | 0.20 | 1000 | 86 | hundreds of tournaments |
| 0.0030 | 2.0% | 0.28 | 400 | 35 | tens of tournaments |
| **0.0050** | **3.4%** | 0.49 | **150** | **13** | **credible threshold** |
| 0.0100 | 6.7% | 0.90 | 58 | 5 | already detectable; not present |

## Recommended acceptance protocol (research threshold, not runtime/trade approval)

- **Pre-registered effect floor:** 0.0050 absolute RPS improvement (the smallest plausibly-real
  effect that 80% power can reach at affordable volume).
- **Minimum independent international matches:** **150** (≈8–13 distinct tournaments).
- **Decision rule:** match-level paired cluster bootstrap; accept iff the two-sided 95% CI on
  `mean(candidate − reference)` RPS lies entirely below 0, **and** calibration_ok, **and** fold
  majority — exactly the gate the residual eval used, just with enough matches behind it.
- **Forbidden:** counting snapshots as independent units; tuning to 2026; substituting club matches
  for international without a separate club power curve.

## Three direct answers

1. **Is 58 enough for the uplift we care about?** No. 58 matches is only well-powered for a *large*
   0.0100 edge that the eval already showed is absent. For small realistic corrections it is
   underpowered (10–28%); the null is uninformative about small true effects.
2. **How many matches for a credible claim?** ~150 international matches for a moderate 0.0050 edge;
   ~400 for 0.0030; ~1000 for 0.0020.
3. **Are more snapshots useful without more matches?** No — power is flat under snapshot inflation.
   Only additional independent matches help.

## Club-only lever

`data_insufficient` — the eval had zero club matches, so no club per-match RPS exists to build a
club power curve. Club football could reach 150+ matches fast, but international-transfer of in-play
dynamics is unproven and would require its own validation before any claim.
