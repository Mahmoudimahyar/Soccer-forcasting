# Tournament Simulator — Known Limitations (Phase 2 / 7C, 2026-06-23)

Honest scope boundaries of the current simulator. None is a correctness bug; each is an explicit
modeling choice or an un-implemented pathway, documented so downstream claims stay within scope.

## Not modeled in the FORWARD simulator
1. **Explicit knockout bracket / R32 routing matrix.** `simulate_group_stage_official` outputs
   advancement probabilities (`p_advance / p_first / p_second / p_third_advance`), NOT the specific
   Round-of-32 pairings or the third-place routing-to-bracket matrix. The R32 mapping is not implemented
   in `simulation/`. → knockout-draw / bracket-path claims are out of scope until added.
2. **Knockout-round progression, extra time, penalty shootout (forward sim).** The forward simulator
   stops at group advancement. Extra-time and shootout are handled in the 2022 **replay** semantics
   (Phase 1, `replay_semantics.shootout_score`), separate from regulation/ET — but the forward simulator
   does not simulate knockout ET/shootout.
3. **Disciplinary/fair-play and FIFA-rank inputs are hooks.** `conduct` and `fifa_rank` are honored by
   the tiebreak engine, but populating them for 2026 from a live disciplinary feed is not wired; absent
   data falls back to neutral (conduct 0, FIFA 999), which only affects deep ties.
4. **Drawing-of-lots final tiebreak.** The official rules' ultimate "drawing of lots" is replaced by a
   deterministic stable fallback (team name) for reproducibility — it never random-draws.

## Modeled correctly (for the record)
- Group standings, points, GD, GF, recursive head-to-head, overall fallback, conduct + FIFA-rank keys.
- Best-third ranking across groups (8 slots).
- Already-qualified/eliminated emerge from the ranking (top-2 advance; 4th never).
- Fixtures with results are fixed; only unplayed fixtures are simulated; re-applying a result is
  idempotent; fully-played groups are deterministic.

## Implication
Use the simulator for **advancement probabilities** and group-state features. Do NOT claim specific
knockout-bracket paths, knockout-round outcomes, or shootout-stage forward simulation until those
pathways are implemented and validated.
