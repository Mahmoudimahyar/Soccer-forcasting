# API-Football — Research Readiness (Phase 5)

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. ACTUAL observed counts from the
**120-match international pilot** (no model trained). Reproduce: quality_audit -> reconcile ->
research_readiness. Per-fixture + readiness CSVs (gitignored): `data/processed/api_football_historical_coverage_summary.csv`,
`data/processed/api_football_research_readiness.csv`.

## Pilot corpus
120 finished international matches (WC2022 + Euro2024 + Copa2024 + AFCON2023 + AsianCup2023), 245/300 requests,
append-only gitignored raw. **Quality: 120/120 with events + lineups + player IDs; duplicate rate 0.0005;
score reconciliation 90% exact** (12 mismatches at ET/shootout/VAR boundaries — informational).

## The 7 research tables (derivable from the pilot raw + coverage summary)
1. match/event — 120 matches, 1,890 events (goals/cards/subs/VAR) with team + player.id + elapsed minute.
2. lineup/substitution — 120/120 startXI + benches + 1,085 substitution events.
3. player-state coverage — 120/120 player IDs; positions present (startXI.pos + /fixtures/players).
4. card/discipline — 432 yellows, 12 reds, 3 second-yellows, **15 red-or-2Y**.
5. event-timeline quality — dup 0.0005; ordering issues 9/120 (ET boundary); reconcile 90% exact.
6. competition coverage — 5 international tournaments; 2,180 finished matches available in-source.
7. source completeness — events+lineups completeness 1.0 for all 120 pilot matches.

## Per-model-class readiness (observed vs adopted threshold)
| class | key metric | pilot | threshold | pilot meets | reachable? |
|---|---|---|---|---|---|
| A player/substitution | matches w/ lineups+player IDs | 120 | 500 | NO | **YES** — 2,180 finished available; quality 100% |
| A | substitution events | 1,085 | — | — | strong density |
| B cards/red | red-or-second-yellow | **15** | 150 | NO | reachable only with ~10x more matches (reds rare; add major leagues) |
| B | yellows | 432 | — | — | abundant |
| C next-goal | timestamped-event matches | 120 | 500 | NO | **YES** — every finished match carries timestamped events |
| C | goals | 302 | — | — | abundant |
| C | shot locations / xG | unavailable / partial | — | NO | **provider GAP** — needs richer provider |
| D in-play W/D/L | score-exact reconcile | 90% | — | — | usable; clean timelines on 120 |

## Honest verdict
- **Quality is excellent**; **thresholds are NOT yet met by the 120-match pilot** but are **reachable for
  player/substitution and next-goal** (W/D/L) with a larger (still bounded) backfill — the data exists and is clean.
- **Cards/red-cards**: yellows abundant, but red-or-2Y density is ~0.125/match -> reaching 150 needs ~1,200
  matches (add major leagues, where reds are more frequent). Largest backfill lift of the four.
- **xG / shot-locations**: API-Football does NOT close this gap (team-level shots only; xG newer-only; no xy).
  xG/shot-quality models remain blocked on this source -> a richer provider (Opta/StatsBomb) or add-on needed.
- Do NOT claim any model is "ready" — these are coverage counts, not trained results. No model was trained.
