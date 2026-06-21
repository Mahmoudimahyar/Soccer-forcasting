# API-Football 2022 WC Event Replay — Report (2026-06-21)

Authenticated free plan, **2022 season only** (free plan covers 2022–2024; never used for 2026).
Raw cache: `data/raw/api_football_2022_worldcup/`; normalized replay: `data/processed/inplay_replay_2022_worldcup.csv`.

## API usage / quota
- **~51 successful requests today** (1 fixtures + 1 events probe + 1 lineups probe + 48 group-match
  events). Well under the **100/day** free limit (~49 remaining; resets daily).
- **Per-minute limit = 10 req/min** (free). First bulk attempt fired too fast and was rate-limited on
  ~34 calls (those returned a rateLimit error, were **not cached**, and do not consume daily quota);
  re-run throttled to ~8.5/min recovered all 48. Lesson encoded for any future ingestion.

## Coverage
| data | status |
|---|---|
| fixtures (IDs, teams, final scores, status, round→matchday) | ✅ 64 fixtures (48 group) |
| match events (goals, cards, subs, VAR) with minute | ✅ **48/48 group matches**, 0 missing |
| lineups (formation, starting XI, substitutes) | ✅ available (probe: 5-3-2, XI=11, subs=15) — not bulk-cached (quota-conscious) |
| match statistics | available on plan (not fetched this run) |
| standings | available on plan (not fetched this run) |
| expected goals (xG) | ❌ not provided by API-Football events |

## Replay table (leakage-safe)
288 rows = 48 matches × 6 decision minutes {15,30,45,60,75,90}. Each row's state uses **only events
with elapsed ≤ decision minute** (`state_from_events`, tested in `test_replay_leakage.py`): current
goals (own-goals credited to opponent, missed penalties ignored), red cards, oriented to team_a.
Pre-match λ from a scoreline mapping fit on **pre-2022** goals only. No post-match summary, no later
events used in earlier rows.

## In-play engine validation (frozen engine vs final outcome, by minute)
| decision minute | n | RPS | log loss |
|---|---|---|---|
| 15 | 48 | 0.2549 | 1.189 |
| 30 | 48 | 0.2291 | 1.106 |
| 45 | 48 | 0.2034 | 1.031 |
| 60 | 48 | 0.1362 | 0.777 |
| 75 | 48 | 0.1030 | 0.619 |
| 90 | 48 | 0.0000 | 0.008 |

**Verdict: the in-play engine is sound.** RPS and log loss fall monotonically as the match
progresses and collapse to ~0 at full time (degenerate to the known result) — exactly the expected
behavior. The transparent remaining-time Poisson engine produces well-ordered, sharpening,
leakage-safe regulation-time probabilities on real 2022 events.

## Data-quality limitations
- **No xG** in API-Football events → the engine's optional xG-surprise adjustment can't be validated
  here (would need a separate xG feed, e.g. StatsBomb open).
- Event minute is integer (no second-level timestamp); stoppage-time goals carry `extra` separately.
- Lineups/statistics/standings are available but not bulk-cached this run (quota).
- Free plan is 2022–2024 only → this path supports **historical** replay, not live 2026.

## Feasibility
**In-play historical replay is feasible and now operational for 2022.** Trustworthy variables for
historical testing: **minute, current score, goals, red cards, substitutions** (all from events).
Not trustworthy/absent: **xG** (missing). Next: optionally bulk-cache lineups (for lineup-time
features) and statistics, within the daily budget via the quota-aware scheduler.

Governance: used only to validate the in-play engine + identify missing data. **Not** used to tune
the approved pre-match B1 model.
