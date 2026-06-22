# Program Work Log

Append-only log of program actions (most recent last).

- 2026-06-21 — Phase A: created program control files (STATE/BACKLOG/WORK_LOG/BLOCKERS/DoD) +
  `PROGRAM_CURRENT_TRUTH.md`. Baseline `pytest -q` = 151 passed at `cff737d`. No protected files touched.
- 2026-06-21 — Phases B-G: API-Football historical adapter; eval framework + data products; multi-competition schema; model registry; collector/scheduler docs. Terminal state: EXTERNALLY BLOCKED (BLK-1..5). Tagged worldcup-predictor-v1-blocked.
- 2026-06-21 — CORRECTION: multi-competition in-play UNBLOCKED on API-Football free tier (Euro2024+Copa2024 added; 108 matches). M2 = SHADOW-CANDIDATE (beats M1 on 3/3 held-out competitions). Deleted premature worldcup-predictor-v1-blocked tag. Player plane still needs paid Pro; more competitions rate-paced by daily quota.
- 2026-06-21 (cont.) — Used existing Odds-API data (intl_market_sharp): made 3-competition in-play set market-aware; added M6 market-anchored in-play. Finding: market ≈ Elo in-play (M6 vs M2 dRPS -0.0004, CI [-0.008,+0.007], NOT significant); both beat M1 on 3/3. Odds API does NOT unblock player plane (no lineups/xG). API-Football at 68/100 today -> 4th competition (AFCON) deferred to next quota window. commit eaf942f.
- 2026-06-21 (cont.) — Added AFCON2023 (partial, 24 matches) as 4th competition/confederation. 4-comp leave-one-competition-out (132 matches): M2 & M6 beat M1 on 4/4 holdouts (M2 dRPS -0.0165 CI [-0.025,-0.008]); market ~= Elo (M6 vs M2 CI incl 0). API-Football quota ~exhausted for the window (reserve held); AFCON completion + Nations League next window.
- 2026-06-21 (cont.) — New 2nd free key API_FOOTBALL_KEY_1 verified WORKING (Free tier, fresh 100/day, NOT 2026/lineups). Used it to complete AFCON2023 (33 matches) + add AFC Asian Cup 2023 (10, partial). Now 5 competitions/5 confederations (151 matches): M2 & M6 beat M1 on 5/5 holdouts (M2 dRPS -0.0145 CI [-0.021,-0.008]). Gold Cup + Asian Cup completion rate-limited (next window). Fixed empty-df guard + --key-env in build_multicomp_inplay.
