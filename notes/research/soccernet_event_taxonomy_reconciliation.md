# SoccerNet Event-Taxonomy Reconciliation (Phase 3)
- Source: SoccerNet Labels-v2.json, 17 action classes. Mapped -> canonical taxonomy
  (schemas/soccernet_event_taxonomy_v1.yaml). 12 canonical types are keyword-evaluable.
- Supported (direct): goal, penalty_awarded, yellow_card, red_card, second_yellow, substitution, corner,
  offside, foul, shot_on_target, shot, kickoff.
- mapped_to_other: Throw-in, Clearance, Ball out of play, Indirect/Direct free-kick.
- **Unsupported by this source** (no class / no field): own_goal, penalty_scored, penalty_missed,
  VAR_review, VAR_goal_cancelled, halftime, fulltime; also NO player IDs in v2 -> entity (Level-2)
  alignment limited to team side.
