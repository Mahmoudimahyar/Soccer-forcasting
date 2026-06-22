# Durable Collector & Scheduler (Phase F)

Restart-safe, low-cost, point-in-time collection for shadow research. **No live trading; research-only.**
Components already exist and are tested; this documents the architecture, scheduling, and the
SHADOW-CANDIDATE bar. Nothing here is launched automatically.

## Components (existing, tested)
- `scripts/five_hour_supervisor.py` — bounded loop, hard credit cap, `--resume-latest` (restart-safe
  via `state.json`), fail-closed with backoff, clean shutdown + `session_summary.json`.
- `scripts/live_2026_shadow.py` — freeze immutable M1–M5 predictions; `score` after results.
- `wcdrawlab.research.shadow_integrity` + `scripts/validate_shadow_integrity.py` — invariants.
- `scripts/shadow_session_close.py` — closure manifest + scorecard.
- Append-only raw store (`wcdrawlab.ingestion.raw_store`); prediction ledger with model_id, source
  hashes, decision timestamp, approval_status; quota-aware scheduler (`providers/schedule.py`).

## Scheduling (do NOT start high-frequency polling)
**Windows Task Scheduler** (run the supervisor once per intended window; it self-bounds):
```
schtasks /Create /TN "wc_shadow_supervisor" /SC ONCE /ST 18:00 ^
  /TR "python C:\Users\Mahyar\worldcup_draw_model_lab_FINAL\scripts\five_hour_supervisor.py --hours 5 --max-credits 30 --resume-latest"
```
**cron** (Linux/macOS), e.g. snapshot freeze near kick-offs + score after finals:
```
*/10 * * * *  cd /path/repo && python scripts/live_2026_shadow.py freeze   # capture due snapshots
5    */1 * * * cd /path/repo && python scripts/live_2026_shadow.py score    # score finished matches
```
Guardrails: ≤30 Odds credits/session, ≥10 min between odds calls, FINISHED-gated results, reserve
quota, idempotent (state file), no trading.

## SHADOW-CANDIDATE criteria (a research model may be *labelled* shadow-candidate ONLY if ALL hold)
1. Beats the appropriate simple baseline (pre-match: B1; in-play: M1 time+score) on **≥2 independent
   competition/time holdouts**.
2. Calibration acceptable (slope≈1, intercept≈0; reliability sane).
3. Gain has **match-level bootstrap** support (CI excludes 0).
4. Uses only data **collectable point-in-time** during a real match.
5. Source reconciliation + data quality acceptable.
6. Stays entirely separate from approved runtime / trading paths.

## Current status
**No model qualifies** (single-tournament evidence; in-play leaders M2/M5 lack a 2nd independent
holdout). SHADOW-CANDIDATE is therefore **blocked on multi-competition data** (BLK-1). When that data
is approved, re-run the in-play ladder with leave-one-competition-out and re-test these criteria.
