# API-Football Reconciliation Remediation (Phase 1)
research_only. Audit: data/processed/api_football_pilot_reconciliation_audit.csv (gitignored). Module:
src/wcdrawlab/research/paid_source/result_semantics.py. 12 deterministic tests pass.

## Root cause of the prior 90% (12/120 mismatches): own_goal_semantics
EVERY one of the 12 prior mismatches contained an Own Goal event. API-Football reports the `team` field on an
Own Goal as the **BENEFICIARY** (the team credited with the goal), NOT the team that scored into its own net.
The prior reconcile INVERTED own goals (credited the opponent of `team`) -> systematic over/under-count.
Example fid=1145515: `Own Goal team=2`, official 0-1 -> crediting `team` directly = 0-1 (correct); the old
inverting logic produced 1-0 (wrong).

## Fix + result
Credit own goals to `team` DIRECTLY, exactly like normal goals (no inversion). After the fix:
**120/120 regulation-exact (100%), 0 exceptions** on the prior pilot. All 120 pilot fixtures were
regulation (no ET/shootout); the corpus backfill will exercise ET/shootout separation (built + tested).

## Exception classes (predeclared; classifier in classify_exception)
regulation_score_semantics_bug · extra_time_score_separation · penalty_shootout_separation ·
own_goal_semantics · VAR_cancelled_or_corrected_goal · provider_event_ordering_only · missing_event ·
duplicate_event · fixture_metadata_mismatch · unresolved_provider_disagreement. Prior pilot now: {} (all exact).

## Release rule
Each fixture either reconciles exactly for its relevant match-result type OR is classified + EXCLUDED from
affected research datasets. Unresolved mismatches are never silently dropped; raw payloads are never rewritten.
