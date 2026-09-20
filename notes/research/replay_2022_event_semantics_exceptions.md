# 2022 Replay Event-Semantics Exceptions (Phase 1 / 7B, 2026-06-23)

Every exception is explicitly classified; none is silently inferred or dropped.

## Class 1 — `not_cached` (16 knockout matches)
Cause: knockout event files are not in the local offline cache (only the 48 group matches were fetched
during the original in-play build). Classification: **data-availability gap**, not a semantics error.
Action: excluded from knockout-dependent research targets; recoverable by a read-only API-Football fetch
(out of scope for this offline sprint). The penalty-shootout path is already implemented + unit-tested,
so knockouts will reconcile once cached.

## Class 2 — non-chronological raw order (18 of 48 cached, INFORMATIONAL)
Cause: API-Football returns events grouped by type (all goals, then cards, then subs), so the raw list
is not minute-monotonic even though the score reconciles exactly. Examples verified by hand:
England 6–2 Iran, Senegal 0–2 Netherlands, USA 1–1 Wales, Argentina 1–2 Saudi Arabia — all reconcile
exactly. Classification: **informational flag only** (`chronological=false`); does NOT fail the release
gate. Reconciliation is order-independent (it sums goals); the in-play state builder sorts by minute and
enforces no-future-leak separately.

## Class 3 — score-reconciliation failures
**None.** All 48 cached matches reconcile exactly (own-goal beneficiary, VAR cancellation, shootout
separation handled).

## Event-semantics rules applied (provider-aware)
- Goal: `Normal Goal` / `Penalty` count; `Own Goal` counts for the recorded team = **beneficiary** (no
  inversion).
- `Var` with "cancel" in the detail nullifies a same-minute, same-team goal.
- Regulation+ET uses minute ≤ 120; **penalty shootout** comes from `fixture.score.penalty`, kept
  separate, never folded into the score.
- Red = `Red Card` or `Second Yellow card` (second yellow also increments the red count).
- Exact-duplicate provider events are de-duplicated before counting.
