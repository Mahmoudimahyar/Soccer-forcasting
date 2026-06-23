# Prospective Collection Activation Report (2026-06-23)

Shadow evaluation + data collection only. **B1 sole approved runtime; M1–M5 are research/shadow;
`KALSHI_ENABLE_LIVE_TRADING=false`; `TRADING_MODE=paper`; no trading path reachable.**

## Provider truth audit (actual)
API-Football is on the **paid Pro plan** (active, renews 2026-07-22; 7/7500/day at audit). 2026 World
Cup fixtures, final-status, events (goals/cards/subs), standings, and lineups all return 2xx. The old
"free tier = 2022–2024 only" note is superseded. The Odds API key is SET and working (h2h/US).
Full detail: `live_provider_truth_audit.md`.

## Collector dry-run result
`fetch_odds_live_2026.py` (no-spend) and `shadow_collector_cycle.py --dry-run` both planned without
spending/writing; root/interpreter/.env/state/dirs verified; no-trading-path + no-overwrite confirmed.
`pytest -q` = **203 passed**. Section-7A integrity = **all_ok**. See `prospective_collector_preflight.md`.

## Scheduler installation result
Installed and **Ready**.
- **Task name:** `WorldCupShadowCollector`
- **Executable:** `powershell.exe -File scripts\windows\run_shadow_collector.ps1` → runs one bounded
  `shadow_collector_cycle.py` (a local Python collector, **not** Claude Code; cannot trade).
- **Working directory:** repo root.
- **Trigger frequency:** every **5 minutes** (wake-to-check only; the cycle enforces all rate/budget limits).
- **Hard end condition:** repetition until **2026-07-04 20:00Z**; the cycle also self-stops past
  `--hard-end-utc` (default 2026-07-05) — covers "after the final group-stage match is scored."
- **Heartbeat:** `outputs/live_shadow/collector_heartbeat.json`
- **State:** `outputs/live_shadow/collector_state.json`
- **Logs:** `outputs/live_shadow/scheduler_logs/`
- **Stop/remove:** `scripts\windows\uninstall_shadow_collector_task.ps1`

## Upcoming fixtures registered
**28 eligible** not-started 2026 group-stage matches (`data/reference/future_2026_prospective_queue.csv`);
44 completed/in-progress excluded from the clean pool.

## Odds API quota / credits
- Provider quota (from response headers): used 6910, **remaining 13090**.
- Our hard study budget: **500 credits**; **used so far = 1** (the verified baseline). Remaining 499.
- **Projected remaining group-stage usage:** ~100–200 credits (T-90 + T-15 per match, batched across
  concurrent matches; sparse ≥120-min baselines). Hard-capped at 500 with fail-closed halt.

## First immutable predictions saved
`outputs/research/live_2026_shadow_predictions.csv`: **400 rows** — 28 upcoming matches × M1–M5 where
market present (104 approved=M1/B1, 296 shadow=M2–M5), each with probabilities, SEs, draw CIs, model
version, approval status, source snapshot timestamp. Immutable (never overwritten after kickoff).

## Safety guards verified
- HALT unless trading flags safe (KALSHI false / paper) — exit 3 otherwise.
- Immutable first-write-wins (odds snapshots + predictions); no overwrite post-kickoff; no duplicates.
- Budget fail-closed (≤500 credits, ≥10-min spacing, ≥120-min baselines), persistent across restarts.
- No secrets logged (names only); raw payloads append-only + gitignored.
- Runtime/trading do not import the operations/shadow plane; no Kalshi order path.
- Section-7A integrity all_ok; 203 tests pass.

## Known provider gaps
- The Odds API: **h2h/1X2 only** (by design here) — no in-play odds, props, totals.
- API-Football Pro: events/lineups present but **xG coverage inconsistent**; not a per-shot xG feed.
- These gaps affect the **player/next-goal/card** model classes, NOT the M1–M5 1X2 shadow study.

## Is a paid provider justified now?
**No.** Per the stated gating conditions, the paid-provider (Sportmonks/StatsBomb/Opta) decision is
deferred until: (1) the collector has captured a meaningful number of remaining 2026 matches, (2) the
M1–M5 comparison has real out-of-sample results, (3) we know whether lineups/events are the dominant
missing signal, and (4) a coverage probe proves a provider fills that exact gap. None are satisfied yet.

## What happens automatically now
Every 5 minutes the task runs one bounded cycle: verify flags → (if a T-90/T-15 window is due and budget
allows) capture one batched odds snapshot → freeze immutable M1–M5 predictions for upcoming matches →
score any FINISHED match (metrics only; Elo/standings updated once per match; never retrains) → write
heartbeat/state/log. It stops at the hard end. To stop early, run the uninstall script.
