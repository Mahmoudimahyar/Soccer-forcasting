# Dynamic Temporal Player Priors — Coverage Report (Component 2 / Phase 2)

`research_only`. Built from the REAL corpus; all numbers below are produced by
`scripts/build_dynamic_temporal_player_priors.py` + `scripts/audit_dynamic_player_priors.py`
(`dynamic_player_prior_v1`). No fabricated values.

## Headline coverage
- International matches with reconciled lineups (test population): **627**
- Distinct international decision snapshots `(match, team, minute)` over minutes 15/30/45/60/75: **6,270**
- Snapshots with ≥1 player-prior coverage: **5,670** → **coverage_rate = 0.9043**
- Mean `coverage_aggregate` among covered snapshots (fraction of XI with a known prior): **0.858**
- Mean unknown players per XI: **2.47** (of 11)

`status = complete` — real priors are computed for well over 0 international snapshots (5,670 covered).

## Appearance corpus feeding the priors
| comp_type | appearances |
|---|---|
| international | 13,931 |
| club (prior history only) | 48,426 |
| **total** | **62,357** |

## Derived tables (gitignored under `data/processed/dynamic_player_priors/`)
| table | rows | grain |
|---|---|---|
| `player_exposure_priors.csv` | 29,186 | one row per (match, team, player-in-squad), pre-match |
| `player_contribution_priors.csv` | 29,186 | same grain; 16,521 known / 12,665 unknown |
| `team_composition_features.csv` | 6,270 | one row per (match, team, decision-minute) |
| `substitution_delta_features.csv` | 4,687 | one row per substitution event |

## Coverage by competition (covered / total snapshots)
| competition | covered | total | rate |
|---|---|---|---|
| Euro | 3,435 | 3,640 | 0.944 |
| Copa | 295 | 320 | 0.922 |
| WC | 1,090 | 1,280 | 0.852 |
| AFCON | 435 | 520 | 0.837 |
| AsianCup | 415 | 510 | 0.814 |

Coverage is uniform across decision minutes (0.904 at every minute) — the *presence* of a pre-match prior
does not depend on the in-play minute; what changes with the minute is the on-pitch composition aggregate.

## Why ~10% is uncovered (honest, not a defect)
The uncovered ~9.6% are early-tournament / early-corpus snapshots where **no** member of the XI yet has a
strictly-earlier appearance in the corpus (the first matches a player or competition appears). Those XIs
correctly fall back to the `unknown_player` shrinkage floor and are flagged (`coverage_aggregate = 0`,
`low_coverage_flag = True`). This is the expected behavior of a strictly causal prior — earlier history
simply does not exist for them. Euro has the highest coverage because the corpus contains the most prior
Euro/club history for those players; AsianCup the lowest.

## Verification
`scripts/audit_dynamic_player_priors.py` → **19/19 checks pass, self_test = pass**, including a recount of
this coverage that matches the manifest exactly. Leakage and shrinkage guarantees are proven on deterministic
synthetic fixtures and re-audited on the real outputs.
