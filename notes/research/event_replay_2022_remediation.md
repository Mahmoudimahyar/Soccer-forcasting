# Event-Replay Correctness Remediation — Own Goals (2026-06-21)

Branch `event-replay-own-goal-fix`. Repairs the derived event-state reconstruction only. Raw payloads
untouched. Not a model/training/API/polling task.

## 1. Root cause (confirmed from raw payload, fixture 855767)
- Match: **Canada (home, id 5529) vs Morocco (away, id 31)**, official **1-2**, Group Stage 3.
- Raw goal events (`data/raw/api_football_2022_worldcup/events_855767.json`):
  - 4'  Goal, Normal Goal, team=Morocco (31), player=H. Ziyech
  - 23' Goal, Normal Goal, team=Morocco (31), player=Y. En-Nesyri
  - 40' Goal, **Own Goal, team=Canada (5529)**, player=N. Aguerd
- **Provider semantics:** API-Football sets the Own Goal `team` field to the **BENEFICIARY** (the team
  credited the goal = Canada). The player (Aguerd) belongs to the opponent (Morocco).
- **Old derived logic** (`state_from_events`): for any Own Goal it credited the **opponent** of the
  reported team → credited Morocco a 3rd goal → derived **Morocco 3-0 (Canada 0-3)** instead of the
  correct **Canada 1-2**. I.e. it **blindly inverted** every own goal, which is wrong for API-Football.

## 2. Correction — provider-aware canonical event layer
New module `src/wcdrawlab/research/event_semantics.py`. Canonical record fields:
`event_team_id_as_reported, beneficiary_team_id, player_team_id_if_known, scoring_team_id,
own_goal_flag, is_goal, provider_name, provider_semantics_version, minute, derived_state_quality_status`.

Versioned own-goal rule (`own-goal-semantics-v1`):
- `api_football` → own-goal `team` = **beneficiary** ⇒ scoring_team = reported team (NO inversion);
  player_team = opponent.
- a `scorer`-encoding provider (explicit) ⇒ scoring_team = opponent.
- **unknown provider ⇒ FAIL CLOSED** (`derived_state_quality_status="unknown_own_goal_semantics"`,
  goal excluded — never guessed).
- standard goal ⇒ scoring_team = reported team. Missed penalty ⇒ not a goal. Cards/subs/VAR ⇒ never
  change score. Provider identity preserved separately from the derived scoring team. Raw payload
  hashes retained in the quality CSV.

`inplay_replay.state_from_events` now delegates goal interpretation to this layer (default provider
`api_football`); red-card/causality logic unchanged.

## 3. Tests (`tests/test_event_semantics.py`, sanitized + 1 real fixture)
Standard goal; API-Football own goal (no inversion); scorer-encoding provider (inversion); unknown
provider fails closed; cards don't score; VAR-cancelled goal excluded; **fixture 855767 → Canada 1-2
Morocco**; event-time causality; idempotency. All pass. A prior test that asserted the *buggy*
inversion (`test_own_goal_credits_opponent...`) was corrected to the proper beneficiary semantics.

## 4. Outcome
Full 2022 rebuild reconciles **48/48 exact** (`scripts/rebuild_replay_2022.py` →
`data/processed/event_replay_2022_quality.csv`). See `event_replay_2022_release_gate.md`.
