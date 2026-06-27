# Residual Goal-Intensity — Regime Coverage Report

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Module: `wcdrawlab.research.residual_intensity.regimes`. Population: the real international event-process
panel — **7,376 snapshots, 58 matches, 5 competitions** (FIFA WC 2018, FIFA WC 2022, UEFA Euro 2020,
UEFA Euro 2024, Copa America 2024). No 2026 World Cup rows (enforced upstream).

## What a regime is (and is NOT)
A regime is a coarse, **interpretable, rule-based** bucket of the match SITUATION at the decision
minute. It is derived ONLY from causal state and source availability:
- **game_state** — from current score diff, remaining regulation minutes, and player-count diff.
- **evidence_tier** — from event-process feature **completeness** (causal availability only) + xG
  presence: `rich >= 0.75`, `partial >= 0.40`, else `sparse`.

It is **deliberately not an outcome model**: it never reads a target, is fully deterministic, and exists
so the intensity / selective families can condition on a few human-readable situations rather than on a
high-dimensional, partly-unavailable feature vector. An outcome-trained "regime" would smuggle label
information into a gating decision; a rule-based one guarantees the gate's confidence cannot rise on label
leakage — only on observable causal state. Manpower regimes (`down_a_man`/`up_a_man`) take precedence
because a sending-off changes the intensity structure most.

## Coverage on the real panel
Combined regime label = `<game_state>|<evidence_tier>`. Observed regimes (rows / distinct matches):

| regime | rows | matches |
|--------|-----:|--------:|
| level_mid \| rich | 1724 | 44 |
| narrow_lead_early \| rich | 1495 | 49 |
| level_early \| rich | 1171 | 52 |
| narrow_lead_late \| rich | 929 | 38 |
| level_late \| rich | 669 | 22 |
| two_plus_lead \| rich | 658 | 23 |
| level_early \| partial | 370 | 58 |
| down_a_man \| rich | 143 | 2 |
| blowout \| rich | 138 | 6 |
| up_a_man \| rich | 79 | 1 |

### game_state marginals
`level_early 1541, level_mid 1724, level_late 669, narrow_lead_early 1495, narrow_lead_late 929,
two_plus_lead 658, blowout 138, down_a_man 143, up_a_man 79`.

### evidence_tier marginals
`rich 7006, partial 370, sparse 0`. The `partial` tier is exactly the 370 no-xG rows — losing the xG
family drops completeness below the `rich` threshold. There are no `sparse` rows in this corpus because
the StatsBomb international snapshots are otherwise structurally complete.

## Honest coverage caveats (small-sample regimes)
These regimes are **thinly populated** and must not be over-trusted by any regime-conditioned model:
- `up_a_man|rich`: 79 rows from **1 match** — a single-match artifact; a regime-specific intensity here
  would be fitting one game.
- `down_a_man|rich`: 143 rows from **2 matches**.
- `blowout|rich`: 138 rows from **6 matches**.

Consequently the `intensity.regime_specific_i2` family must pool / shrink small regimes toward the W2
reference (or the all-rows intensity) rather than fitting a free per-regime model; any per-regime estimate
backed by `< ~5 matches` should be reported as `data_insufficient` for that regime rather than emitted as
a confident number. The regime label is most useful as a *gating / stratification* signal and a coverage
diagnostic, not as a standalone predictor on this corpus.

## Tie to the selective gate
The `evidence_tier` axis is the same causal-availability signal the selective gate uses to cap
correction: a `partial` (no-xG) row carries less event-process evidence, so the gate maps it to a
**lower-or-equal** correction band — never a higher one. Completeness is monotonically tied to the
correction weight, so a sparser row can only receive a smaller `alpha` (see the selective-correction data
card).
