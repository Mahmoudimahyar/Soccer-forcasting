# API-Football — Empirical Coverage Audit (Phase 1, 2026-06-26)

research_only / not_runtime_approved / not_live_eligible. **27 read-only requests** (cap 30) via the existing
`ApiFootballReadOnly` adapter (key never printed; raw appended to gitignored `data/raw/api_football_audit/`).
Plan confirmed from `/status`: **Pro, 7,500 requests/day**. Data: `data/reference/api_football_empirical_coverage.{csv,json}`.

## Method
Known league IDs (avoids non-allowlisted `/leagues`). 1 `/status` + 1 `/fixtures` per competition-season (11)
+ deep sample (events/lineups, plus statistics+players for WC/Euro) on the 5 international tournaments + UCL
control. One representative finished fixture per deep sample (no bulk download).

## Fixture/competition availability (all available_verified)
| competition | fixtures | finished | timestamp | final score |
|---|---|---|---|---|
| FIFA WC 2022 | 64 | 59 | yes | yes |
| UEFA Euro 2024 | 51 | 46 | yes | yes |
| Copa America 2024 | 32 | 27 | yes | yes |
| AFCON 2023 | 52 | 46 | yes | yes |
| AFC Asian Cup 2023 | 51 | 46 | yes | yes |
| UCL 2023-24 | 214 | 202 | yes | yes |
| EPL / LaLiga / Bundesliga / SerieA / Ligue1 2023-24 | 380/380/308/380/308 | ~all | yes | yes |

## Field classification (from observed samples)
| field | class | evidence |
|---|---|---|
| fixtures / timestamps / final score | available_verified | every competition above |
| event timeline (goals, cards, subs) | available_verified | all 6 deep samples carry goal+card+subst with player.id + time.elapsed |
| substitutions | available_verified | subst events present in all deep samples |
| lineups (startXI) | available_verified | all 6 deep samples |
| benches (substitutes) | available_verified | all 6 deep samples |
| player IDs | available_verified | startXI[].player.id present in all 6 |
| player positions | available_verified | startXI[].player.pos + /fixtures/players games.position (WC22) |
| formation | available_verified | all 6 deep samples |
| VAR events | available_partial | present in WC22 + Euro24 samples; not in the single sampled fixture of others |
| own goals | available_partial | own-goal detail present in Euro24 sample (schema supports); rare per fixture -> counts need volume |
| red cards | available_partial | red present in Euro24 sample; rare per fixture -> counts need volume |
| second yellows | unknown_requires_more_sampling | not isolated in single-fixture samples; resolve via backfill (Phase 3) |
| team shots | available_verified | /fixtures/statistics WC22 + Euro24 (shots present) |
| **xG** | **available_partial** | Euro24 statistics HAD expected_goals; WC22 did NOT -> competition/era-dependent |
| **shot locations (xy)** | **unavailable_verified** | API-Football statistics are TEAM-level; no per-shot coordinates anywhere |
| injuries | unknown_requires_more_sampling | not sampled (separate endpoint, not in read-only allowlist) |
| event corrections | unknown_requires_more_sampling | needs repeated snapshots over time (Phase 2/3) |

## Headline
API-Football Pro covers the **player / substitution / card / next-goal MUST-HAVES** (lineups + benches +
player IDs + positions + timestamped events) for ALL five target international tournaments + club leagues.
**Gaps: shot locations (never) and xG (partial — newer tournaments only).** Own-goal / red / 2nd-yellow
COUNTS require the historical backfill (Phase 3) to verify the >=150 threshold.
