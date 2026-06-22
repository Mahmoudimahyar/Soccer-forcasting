# Player-Plane Results (research-only, 2026-06-22)

Unblocked by the **paid API-Football Pro plan** (lineups + per-player stats + team xG + 2026; ToS-clean,
single account). Built a leakage-safe player-plane feature pipeline and tested whether player-level
information improves the **pre-match 1X2** forecast beyond Elo.

## Data
Lineups / per-player ratings / team xG fetched for finished matches of 5 tournaments
(WC2022, Euro2024, Copa2024, AFCON2023, AsianCup2023): **224 matches** with lineups; Elo resolved for
220; usable rows (Elo + player features present) = **166**.

## Leakage discipline (enforced + unit-tested)
- Starting XI + formation: from `/fixtures/lineups`, published ~1h **before** kickoff → legal pre-match.
- `strength_diff`: mean **prior-match** rating of the announced XI, using only matches that kicked off
  **strictly before** this one. A player's same-match (or any later) rating is never used.
- `keyavail_diff`: fraction of each team's top-6 players (by **prior** cumulative minutes) who start
  today — captures rotation / key absences, which Elo cannot see.
- Team xG is a FINAL total → stored as an outcome column only, **never a feature**.
- Tests: `tests/test_player_plane.py` (8 cases incl. explicit future-rating-never-leaks checks).

## Result — leave-one-COMPETITION-out (lower RPS = better), vs Elo-only baseline
| model | RPS | dRPS vs Elo | bootstrap CI | verdict |
|---|---|---|---|---|
| Elo-only (baseline) | 0.2126 | — | — | — |
| Elo + XI strength | 0.2148 | +0.0022 | [+0.000, +0.005] | **worse** (sig) |
| Elo + key-availability | 0.2123 | −0.0004 | [−0.004, +0.003] | not significant |
| Elo + strength + keyavail | 0.2154 | +0.0027 | [−0.003, +0.009] | not significant |

## Honest conclusion
**No pre-match player feature derivable from API-Football beats Elo on this sample.** Mean prior-match
rating is a weak, noisy quality proxy and largely redundant with Elo; key-player availability is the
least bad (neutral) but not significant. Why: (1) Elo already encodes team strength; (2) international
squads are fairly stable game-to-game, so XI variation carries little orthogonal 1X2 signal at this
resolution; (3) only ~5 tournaments of international history makes prior-form/key-player estimates
noisy. This is a **negative result, recorded as such** — not promoted.

## What this does NOT rule out (next steps)
- xG as a *rating-update* signal (xG-informed Elo) rather than a same-match feature — needs more history.
- The in-play plane is where measurable improvement already exists (M2/M6 beat M1 on 5/5 competitions).
- The decisive test now: validate the in-play models on the **live 2026 World Cup** as true hold-out.
