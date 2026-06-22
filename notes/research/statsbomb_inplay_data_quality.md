# StatsBomb In-Play Dataset Data Quality (Phase 4, 2026-06-22)

Data provided by StatsBomb (non-commercial research). Built by `scripts/build_statsbomb_inplay.py`.

- international: **314 matches / 5966 rows** (6 modern men's tournaments)
- club auxiliary (bounded sample): **60 matches / 1140 rows** (La Liga 2015/16)
- target tables: next_goal/card/sub = 7106 rows each; match_targets = 374

## Integrity checks
- intl elo-resolved: **5738/5966 (96.2%)**
- club elo-resolved: **0/1140 (national-team Elo only -> club unrated)**
- every state row has next_goal target: **True**
- every match has a final target: **True**
- all state rows carry source_events_sha256: **True**
- decision grid per match (intl): **True**
- score never negative: **True**
- competition_type present: **{'club', 'international'}**

## Known limitations (honest)
- **Club rows have NO Elo anchor** (elo_history is national-team only) -> Elo-anchored models cannot
  train/predict on club; club->international transfer via these models is not feasible without a club
  rating source. The club state (score/cards/subs/xG) is still built for non-Elo analyses.
- ~4% of international rows lack an Elo match (rare team-name/date gaps) -> dropped in evaluation.
- Decision points are a deterministic 5-min grid (5..95); state at minute m uses events with minute<m.