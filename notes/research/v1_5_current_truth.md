# V1.5 Current Truth (Phase 0, 2026-06-23)

Reconciliation of state at the start of the V1.5 Prospective-Operations sprint. Branch
`v1-5-prospective-operations` (off `evaluation-reset-event-expansion` @ `e586a05`).

## Models / governance
- **Runtime: B1 ternary-Elo (r=0.4) — SOLE approved pre-match model.** Unchanged; protected.
- **Operative prospective in-play model: `m2_frozen` (M2_RemainingPoisson), frozen v2** —
  `configs/final_holdout_model_m2.yaml`, manifest `final_holdout_freeze_manifest_v2.json`.
  research_only / experimental / not_runtime_approved. Parameter-free (base 1.35, k 0.20, no temp) →
  no 2026 result can change it. v1 (`m2fit_temp`) retained as historical record only.
- Paper-only: `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`.

## What the eval-reset sprint established (tagged `evaluation-reset-event-expansion`)
- Earlier "M2fit_temp is best" = **selection-on-test**; under nested CV it is never selected. **Plain M2
  is the reference**; xG adds nothing (6 pre-registered families ns). In-play ≫ static B1 is the one
  robust, sizeable gain. (`inplay_evaluation_reconciliation.md`, `inplay_nested_evaluation.md`,
  `inplay_result_status_registry.yaml`.)

## Data assets
- StatsBomb in-play (research): 6 modern men's international tournaments = 314 matches + 60-match La
  Liga club auxiliary; next-goal/card/sub/match target tables; player-state coverage. Raw gitignored.
- API-Football: **PAID Pro plan active** (7500/day, all seasons incl 2026, lineups, events, some xG).
- elo_history (national-team Elo, →2026), market_features_2026, pre-match forecast_ledger.csv (B7/market).

## Blockers reconciled (Pro plan changed several)
- BLK-3 (live 2026 events): **RESOLVED** — Pro plan serves 2026.
- BLK-2 (lineups/events): **RESOLVED via API-Football Pro** (xG coverage still inconsistent by comp).
- BLK-1 (multi-competition events): **RESOLVED** for modern men's international via StatsBomb + Pro.
- **Still blocked:** player/next-goal/card model *thresholds* (StatsBomb men's-international ceiling
  ~333 < 500; reds 50 < 150) → need a PAID event provider; club ratings (no club Elo); pre-2020 dev-fold
  odds (BLK-4, unavailable); future-2026 results (time-gated).

## Prospective pool
- 2026 WC fixtures via API-Football: 41 FINISHED (seen → exploratory), 1 live, **30 not-started (NS) =
  clean prospective pool** at last check. Knockouts not yet scheduled will add more.

## Build/verify state
- Last successful test: `pytest -q` = **185 passed**.
- Last stable commit: `e586a05`. Working tree clean at sprint start.

## This sprint (V1.5) goal
Make the lab *operationally ready* to score the frozen M2 prospectively on future 2026 matches: a
durable restart-safe collector, scheduler materials (not auto-installed), a future-fixture queue, a
data-procurement decision package, and a readiness audit — without changing the frozen model, trading,
or any protected file.
