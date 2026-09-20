# Tournament Simulator Validation (Phase 2 / 7C, 2026-06-23)

Validates the OFFICIAL 2026 standings/tiebreak engine + group-stage simulator independently of model
quality, using deterministic synthetic cases. Engine: `wcdrawlab.simulation.official_standings`
(`OfficialGroupTable`, `rank_third_place_official`, `simulate_group_stage_official`,
`force_match_outcome_official`). Validator: `scripts/validate_tournament_simulator.py`; tests:
`tests/test_tournament_simulator_validation.py` (7 cases). All checks PASS.

## Validated pathways
| # | pathway | how validated |
|---|---|---|
| 1 | four-team group standings (points) | round-robin → ranked() == expected order |
| 2 | points accumulation (3/1/0) | `_overall` win/draw/loss points |
| 3 | goal difference | tie broken by GD when H2H drawn |
| 4 | goals scored | GF used after GD in ordering |
| 5 | head-to-head (recursive) | two teams equal on points+GD+GF → H2H winner ranks higher |
| 6 | overall fallback | H2H-drawn pair → overall GD/GF decides |
| 7 | conduct (fair-play) tiebreak | all equal incl GD/GF/H2H → higher conduct ranks higher |
| 8 | FIFA-rank final tiebreak | implemented as last key in `_order_tied` / third-place sort |
| 9 | best-third qualification | `rank_third_place_official` orders thirds by pts/GD/GF/conduct/FIFA |
| 10 | already-qualified / eliminated state | top-2 always advance; 4th never advances |
| 11 | simultaneous final-matchday | all fixtures applied per simulation → no in-sim ordering leakage |
| 12 | idempotent finalize | re-applying the same forced result yields identical goals |
| 13 | no update before FINISHED | only fixtures with non-NaN goals are used as fixed results |
| 14 | determinism when fully played | fully-played group → p_advance identical across seeds/n_sims |

## Notes
- The engine is the ACTIVE 2026 simulator (`simulate_group_stage_official`); the legacy
  `standings.py`/`group_simulator.py` remain baselines only.
- Twelve-group / best-8-thirds format is exercised in production via `simulate_group_stage_official`
  (third_place_slots=8); the synthetic tests validate the per-group + cross-group ranking logic that
  composes it.

See `tournament_simulator_known_limitations.md` for what is intentionally NOT modeled.
