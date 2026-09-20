# API-Football Historical Corpus and Reconciliation Gate V1 — Completion

research_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true ·
KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Worktree `C:/Users/Mahyar/worldcup-api-football-corpus`, branch `api-football-historical-corpus-v1`.

## Active-collector isolation result (verified)
Collector untouched: main checkout `worldcup_draw_model_lab_FINAL`, `v1-5-prospective-operations` @ **dc73318**,
tracked-clean, task **Ready**, heartbeat advancing (…06:33Z). `git diff dc73318..HEAD` = **33 Added, 0
Modified** — no collector code/scheduler/forecast/ledger changed. **No Odds API call made** (API-Football
only). No key revealed (SET/MISSING only). 23 new tests pass; the only failing tests
(`test_inplay_dataset.py`) are PRE-EXISTING in dc73318 and fail solely because their gitignored data is absent
in a fresh worktree (documented artifact, not a regression). B1 sole runtime; M1-M5 + frozen M2 unchanged.

## API call budget & actual use
Plan Pro, 7,500/day; observed remaining 7,229 -> reserve 1,808, research_budget 4,200. Used this sprint:
~13 (Phase 2 lists/status) + **1,800 backfill (events+lineups)** = ~1,813. Well within budget; >5,400 reserved.

## Corpus fixture counts
Predeclared manifest: 2,100 included (627 international Cohort A + 1,473 club Cohort B), 283 truncated.
Backfilled this run: **900 fixtures** (627 international = all Cohort A + 273 club, per the per-run 1,800-request
cap). 1,200 included fixtures remain (resume-able). Raw append-only + gitignored.

## International vs club coverage
- International (627): 627/627 events + lineups + player IDs + bench; 618 positions.
- Club (273): 273/273 events + lineups + player IDs + positions + bench.

## Score reconciliation result
**100% regulation-exact: 900/900 fixtures (627 intl + 273 club), 0 unresolved exceptions.** The Phase-1
own-goal beneficiary fix (API-Football `team` = beneficiary; do NOT invert) holds at scale, with 33 shootout +
12 extra-time fixtures correctly SEPARATED (regulation targets exclude ET/shootout). Prior pilot was 90%.

## Unresolved exception count
**0.** (No fixture required exclusion from affected datasets.)

## Lineup / substitution / player coverage
~100% lineup + bench + player IDs (positions 618/627 intl, 273/273 club). Substitutions: 7,178 total
(4,687 intl + 2,491 club). Goals (regulation): 2,543.

## Card / red-card counts
Yellow cards 3,419 (2,250 intl + 1,169 club). **Sendings-off (direct red + 2nd-yellow red) = 123** (75 intl +
48 club).

## Readiness
- **Player/substitution: READY** — 900 complete lineup/sub matches >= 500.
- **Next-goal (regulation): READY** — 900 clean timestamped, 100% reconciled, >= 500.
- **In-play W/D/L (regulation): READY** — 900 clean regulation matches, 100% exact, >= 500.
- **Card/red: NOT ready (close)** — 123 sendings-off < 150; reachable by resuming over the remaining 1,200
  (club-heavy) included fixtures. Yellows abundant.
- **xG / shot-quality: BLOCKED (gap)** — API-Football has no per-shot xG/locations; not inferred.

## Exact next recommended model sprint
"API-Football In-Play Regulation Baselines V1": resume the backfill to close the red-card gap (>=150
sendings-off), then build leakage-safe baseline models for player/substitution, next-goal (regulation hazard),
and in-play regulation W/D/L with lineup state — competition-level holdouts, calibration on training folds only,
NO promotion to runtime. (xG/shot-quality stays blocked pending a richer provider.)

## What must remain frozen / why trading stays disabled
Frozen + unchanged: M1-M5, prospective in-play M2, B1 (sole runtime), candidate.py, approved_models.yaml,
collector code/task/cadence/odds-windows/odds-budget/ledgers, and all trading/risk/Kalshi/paper code. Trading
stays disabled (KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper): this is historical research only — no
per-event publication time + no causal-gated shadow exist, so nothing here is live or trade eligible. No model
was trained or promoted.
