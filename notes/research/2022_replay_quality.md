# 2022 WC Event-Replay Data Quality (2026-06-21)

From cached API-Football events (`data/raw/api_football_2022_worldcup/`), read-only. Reproduce:
`python scripts/replay_quality_2022.py`. Used to validate the in-play replay; NOT to tune B1.

## Coverage
- Group fixtures: **48/48** have cached events. Total events: **744**.
- Events missing a minute (`elapsed`): **0** — timestamping is complete (clean for time-gating).

## Missingness / coverage by event type
| event type | count | notes |
|---|---|---|
| substitution (`subst`) | 430 | ~9/match — full sub coverage |
| Card | 170 | yellows + reds |
| Goal | 120 | 2.5/match |
| Var | 24 | VAR review markers |
| **red cards** | **2** | genuinely rare in 2022 group stage (low-N for red-card modeling) |
| **lineups** | **0 cached** | not bulk-fetched (events suffice for state replay); available on the free plan if needed |

## Goal reconciliation (events vs final score)
- **47/48** matches reconcile exactly (event-derived score == final score).
- **1 mismatch** (fixture 855767: final 1-2 vs event-count 0-3) — an own-goal / VAR-attribution edge
  case. **Impact: none on scoring** — the replay scores the FINAL outcome from the fixture's official
  full-time score, not the event count; only that match's *intermediate* state is approximate. Flagged
  as a 2% reconciliation anomaly to investigate before using event-derived scores as a primary signal.

## Leakage check
- Replay table (288 rows): per match, `goals_a_so_far`/`goals_b_so_far` are **monotonic
  non-decreasing across decision minutes** → no future event leaks into an earlier row. ✅
- t=90 rows hold the full-match state and are used **only** to score the known final outcome.
- State builder (`state_from_events`) includes only events with `elapsed <= decision_minute`
  (unit-tested in `tests/test_replay_leakage.py`).

## Trustworthy for historical in-play testing
- **Trustworthy:** minute, current score, goals, substitutions, cards (yellow), match clock.
- **Low-N:** red cards (only 2 in 48 group matches) — insufficient alone for a red-card response model.
- **Absent:** xG (API-Football events carry none) → engine's xG-surprise term unvalidated here.
- **Not fetched:** lineups/statistics (available; deferred to stay within the daily quota).

## Verdict
The 2022 event replay is **high quality and leakage-safe** for validating the in-play engine
(already shown to sharpen monotonically t=15→90). Next data-quality steps: bulk-cache lineups for
lineup-time features; obtain an xG source (e.g., StatsBomb open) for the xG-adjustment path;
investigate the single goal-reconciliation anomaly.
