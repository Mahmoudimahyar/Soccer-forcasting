# API-Football Result Semantics Policy (Phase 1)
provider_semantics_version = api_football_result_v1. research_only.

## Goal attribution
- Normal goals: credit the event `team`.
- **Own goals: credit the event `team` DIRECTLY** (API-Football already sets `team` = beneficiary). No inversion.
- Penalty (scored): counts as a goal. Missed/cancelled penalty (detail contains "missed"/"cancel"): NOT a goal.

## Period separation (never mixed)
- regulation: goal events with 0 < elapsed <= 90 (stoppage = elapsed 90 + `extra`). Truth = score.fulltime.
- extra_time: goal events with 90 < elapsed <= 120. Truth = score.extratime. Preserved separately.
- penalty_shootout: from OFFICIAL score.penalty ONLY (never events). NEVER a regulation or next-goal target.
- final_result_type in {regulation, after_extra_time, penalty_shootout}.

## Canonical record fields (per fixture)
official_regulation_home/away (score.fulltime), official_after_extra_time_home/away (score.extratime),
penalty_shootout_home/away (score.penalty), final_result_type, event_derived_regulation_home/away,
event_derived_extra_time_home/away, reconciliation_status, reconciliation_exception_type, source_hash
(on raw), provider_semantics_version.

## Targets
- next-goal / regulation-W-D-L targets use REGULATION goals only (elapsed <= 90), never ET or shootout.
- Extra-time + shootout kept in a separate exception/extension table.
- Provider-reported `team` is preserved separately from any derived beneficiary/scoring-team identity.
