# In-Play Data Products 2022 — manifest (research-only)

Built by `scripts/build_inplay_data_products_2022.py` from the validated 2022 state table.
Products written to `data/processed/inplay_products_2022/` (gitignored).

| product | status | rows | cols | note |
|---|---|---|---|---|
| pre_match_state | available | 48 | 14 | ready |
| inplay_team_state | available | 858 | 19 | ready |
| event_horizon_targets | available | 858 | 15 | ready |
| card_discipline_targets | available_low_signal | 858 | 14 | red targets <1% positive -> not modelable |
| substitution_state | available_counts_only | 858 | 9 | no player IDs/positions -> impact not modelable |
| player_on_pitch_state | blocked | 0 | 0 | BLOCKED: no on-pitch player IDs/positions in available feed |
| weather_travel_context | blocked | 0 | 0 | BLOCKED: venue weather not joined (archive fetch not approved) |
| tournament_qualification_state | partial_prematch_only | 0 | 0 | BLOCKED: in-play qualification state needs group-stage live standings |
