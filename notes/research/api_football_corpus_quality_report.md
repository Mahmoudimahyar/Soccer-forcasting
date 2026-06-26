# API-Football Corpus — Quality Report (Phase 5)

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. Counts observed from the
backfilled corpus (no model trained). CSVs (gitignored): data/processed/api_football_corpus_quality_summary.csv,
data/processed/api_football_model_readiness.csv.

## Corpus
900 fixtures backfilled this run (per-run cap 1,800 requests): **627 international (all of Cohort A) + 273
club** (Cohort B rotation tranche). 1,200 included fixtures remain (resume-able). Raw append-only + gitignored.

## Per-cohort quality
| metric | international (627) | club (273) |
|---|---|---|
| with events / lineups / player IDs | 627 / 627 / 627 | 273 / 273 / 273 |
| with positions / bench | 618 / 627 | 273 / 273 |
| **regulation-score exact reconciliation** | **627/627 = 1.000** | **273/273 = 1.000** |
| substitutions | 4,687 | 2,491 |
| yellow cards | 2,250 | 1,169 |
| sendings-off (direct red + 2nd-yellow red) | 75 | 48 |
| goals (regulation) | 1,726 | 817 |
| extra-time fixtures | 12 | 0 |
| shootout fixtures | 33 | 0 |
| **unresolved exceptions** | **0** | **0** |
| duplicate-event rate | ~0 | ~0 |

## Headline
**100% regulation reconciliation across all 900 fixtures, 0 unresolved exceptions** — the Phase-1 own-goal
beneficiary fix holds at scale, including 33 shootout + 12 extra-time fixtures correctly separated (regulation
targets exclude ET/shootout). Lineup/player-ID/position/bench coverage ~100%. xG / shot-locations remain
unavailable (provider gap; not inferred).
