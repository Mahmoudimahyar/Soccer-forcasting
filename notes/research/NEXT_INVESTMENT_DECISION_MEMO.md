# Next-investment decision memo — evidence-power consolidation

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Decision matrix: `data/reference/next_investment_decision_matrix.json`.
Evidence: Phase 5 power analysis (`match_level_power_analysis.json`,
`minimum_evidence_requirements.json`) + Phase 6 live-readiness
(`live_readiness_matrix.{csv,json}`). **No 2026 WC data. No market claims. No provider purchase
recommendation** — providers are named only to describe a required data class, and those items are
NO-GO for now.

## Bottom line

**Spend effort on MATCHES, not features.** The match-level power analysis is unambiguous: at 58
international matches we can only detect a *large* 0.0100 RPS edge (~90% power) that the residual
eval already showed is **absent**; a credible *moderate* 0.0050 edge needs **~150 matches**, and
adding snapshots to the existing 58 matches buys **no power** (clustering ceiling). Meanwhile **258
exactly-reconciled international matches with verified xG already sit on disk** — only **58** were
materialized into the snapshot panel. The cheapest, highest-information move requires **no new data
purchase at all**.

## Ranked recommendations (information gain per unit effort)

| Rank | ID | Recommendation | Gain | Effort | Go/No-Go |
|---|---|---|---|---|---|
| 1 | **A** | Materialize the ~200 already-bridged international matches into the panel | very high | low | **GO** |
| 2 | B | Add more exact-international tournaments (AFCON/AsianCup/Gold Cup/quals) | high | medium | GO after A |
| 3 | C | Live event-publication **latency study** on the 6 potentially-live families | high | medium | **GO** |
| 4 | D | Re-run power as a **pre-registered sequential acceptance gate** at each N | med-high | low | **GO** |
| 5 | E | Scope a **club** power curve as a separate track (not a substitute) | medium | medium | conditional |
| 6 | F | Acquire a live **xG / spatial** feed for xG + chain families | low | high | **NO-GO now** |
| 7 | G | Acquire **in-play odds** history + **as-of weather** | low | high | **NO-GO now** |

## Why this order

- **A is rank 1** because it directly attacks the only lever that moves power (match count) using
  data already paid for and on disk. It takes power for a 0.0050 edge from 0.49 → >0.8 and gives the
  first genuine chance to detect *or* rule out a moderate in-play correction.
- **B** continues the same lever past the ~150-match credibility line and adds confederation
  diversity for LOCO generalization. Gated by exact reconciliation + full event timelines.
- **C** is the only thing standing between the 6 `potentially_live` families and a defensible
  `live_eligible` claim: no live event-publication latency has **ever** been measured. Cheap,
  necessary, independent of A/B.
- **D** keeps the program honest: the power script is deterministic and cheap, so re-running it at
  each new-N checkpoint pre-commits the 0.0050 effect floor and blocks post-hoc N-shopping.
- **E** is a high-volume sandbox with an explicit **transfer caveat** — club ≠ international.
- **F and G are NO-GO now.** In-play xG and the player/lineup plane are **prior honest negatives**
  vs score+Elo; spatial/odds/weather feeds are expensive and unproven. Revisit **only** if, after
  A/B raise N, a power-adequate re-test finds one of these families beating the reference with a CI
  excluding zero.

## Falsifiers (each recommendation can be killed by evidence)

- **A/B:** if the full ~258-match (and broadened) panel still yields **no** candidate beating the
  W2 reference with a match-level CI excluding 0 at N≥150, the in-play residual-correction thesis is
  **falsified at the moderate-effect scale** — a clean, publishable negative.
- **C:** if measured live latency exceeds the per-family budget (e.g. cards/score >15s) on ≥20 live
  matches, those families are `blocked_by_latency` and live use is off the table.
- **D:** if achieved power never reaches 0.8 for the pre-registered floor at max attainable N,
  declare the edge **undetectable** rather than keep searching.
- **E:** zero/negative club→international transfer ⇒ the club track does not advance the claim.
- **F/G:** absent a power-gated win on the expanded sample, the spend stays unjustified.

## Guardrails

All artifacts remain `research_only / not_runtime_approved / not_trade_eligible /
not_live_eligible`. B1 stays the sole runtime; M1–M5 frozen; the live collector, `.env`, trading/
Kalshi/risk untouched. This memo is an evidence-prioritization document, not an approval to deploy
or trade anything.
