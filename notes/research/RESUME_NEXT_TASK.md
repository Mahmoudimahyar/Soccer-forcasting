# Resume — exact next task

**State: World Cup Predictor V1 is EXTERNALLY BLOCKED** (tag `worldcup-predictor-v1-blocked`, commit
`e42f7e3`+). All unblocked work is complete. `pytest -q` = 159 passed. B1 sole approved; paper-only.

## To resume, FIRST unblock data (your action), then run the matching task:

1. **If you approve StatsBomb open data** (BLK-1, free, non-commercial sign-off):
   - build a read-only loader (no scraping; direct repo download) into the multi-competition schema
     (`schemas/multi_competition_event_schema.yaml`);
   - extend `scripts/build_inplay_state_2022.py` → multi-competition state builder;
   - re-run the in-play ladder (M0–M5) with **leave-one-competition-out** + match-level bootstrap
     (`inplay_eval.py`); test SHADOW-CANDIDATE criteria (`DURABLE_COLLECTOR_AND_SCHEDULER.md`).

2. **If you approve API-Football Pro** (BLK-2/BLK-3, ~$25–30/mo):
   - use `scripts/ingest_api_football_historical.py` (already season-gated/dry-run-tested) — lift the
     2022–2024 gate to include 2026 once the plan covers it; ingest lineups/events/xG-where-available;
     add shots/lineup columns to the state builder.

3. **If neither approved:** the program stays paused (no scientifically valid in-play/player progress
   is possible on 2022 alone). Pre-match B1 remains the approved runtime model.

Do NOT: enable live trading, modify candidate.py/approved routing/trading/risk/.env, scrape, or start
a live session without explicit approval. Full detail: `PROGRAM_V1_EXTERNAL_BLOCKERS.md`,
`PROGRAM_STATE.yaml`, `PROGRAM_BLOCKERS.md`.
