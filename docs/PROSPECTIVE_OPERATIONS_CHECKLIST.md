# Prospective Operations Checklist (V1.5)

Before activating prospective collection for the 2026 World Cup. Everything is research_only; B1 stays
the sole runtime model; trading stays paper/disabled.

## Pre-activation
- [ ] `python -m pytest -q` passes.
- [ ] `python scripts/prospective_integrity_check.py` → INTEGRITY OK (empty ledger is fine).
- [ ] Frozen model present: `configs/final_holdout_model_m2.yaml` (model_id `m2_frozen`, v2).
- [ ] Future queue present: `data/reference/future_2026_prospective_queue.csv` (Phase 4).
- [ ] Dry-run shows a sensible plan: `python scripts/prospective_collect.py`.
- [ ] `.env` has `API_FOOTBALL_KEY` (only needed for in-play capture; pre-match is deterministic).
- [ ] Confirm `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`.

## Activation (your decision)
- [ ] Install scheduler: `install_windows_task_scheduler.ps1` OR a cron line (see setup docs).
- [ ] Leave in dry-run for one cycle; inspect `data/processed/prospective/sessions/`.
- [ ] Enable capture with `EXECUTE=1` when satisfied.
- [ ] (In-play only) confirm a verified live event source before relying on in-play snapshots.

## During the tournament
- [ ] Spot-check the heartbeat is recent.
- [ ] `prospective_integrity_check.py` stays green (first-write-wins, point-in-time safe, no secrets).
- [ ] After matchdays: `prospective_score.py` to grade FINISHED matches (metrics only).

## Hard guarantees (do not override)
- [ ] No trading, ever (paper-only; Kalshi disabled).
- [ ] The frozen M2 is never retrained or reselected from 2026 results.
- [ ] Completed-before-freeze 2026 matches are NOT in the clean prospective pool.
- [ ] Research output never reaches runtime / paper-trade / risk / Kalshi paths.

## Deactivation
- [ ] `uninstall_windows_task_scheduler.ps1` or remove the cron line.
