# Shadow Session 2026-06-21 — Closure Report

Finalization + forensic audit only. No resume, no relaunch, no new Odds API calls, no model/govern-
ance changes. Supervisor self-stopped at the deadline; no process needed termination. Immutable
manifest: `outputs/live_shadow/session_20260621T182402Z/session_close_manifest.json`.

## Session facts
- session_id: `session_20260621T182402Z`
- start: 2026-06-21T18:24:02Z · deadline: 23:24:02Z · actual stop: **23:24:29Z** (self-finalized)
- supervisor status: **completed (ran through the deadline)**
- Odds credits: **7 / 30** (cap not exceeded) · provider calls: Odds API 7, football-data polled
  (no credit cost), API-Football 0, Open-Meteo 0
- snapshots captured: 40 supervisor rows across types {baseline, T-90, T-15, final_pre_kickoff} +
  171 pre-supervisor manual-freeze rows → **372 prediction rows, all strictly pre-kickoff**
- fixtures finalized (recorded idempotently): 38 (MD1 + completed MD2, incl. Belgium–Iran 0-0)
- failures/retries: **0**

## The nine questions — answered plainly
1. **Did the supervisor run through the deadline?** **Yes** — 18:24:02Z → 23:24:29Z, self-finalized
   (`session_summary.json` + "SUPERVISOR DONE"). Caveat: my **first launch (nohup) died after ~6 s**;
   the **harness-managed background relaunch** ran the full 5 hours. The restart-safe state file made
   the relaunch resume the same session with no duplicate Elo updates.
2. **Were snapshots missed because the nohup process died?** **No snapshot was lost to the nohup
   death.** The baseline batch was captured at 18:24 before it died; the next due snapshot (BelIra
   T-15 ~18:45) was captured by the relaunched process at 18:40. BelIra's **baseline + T-90 are
   MISSED_UNRECOVERABLE**, but because the **session started at 18:24Z — after BelIra's T-90 (17:30Z)
   and inside its <100-min baseline window** — not because of the nohup death. Not backfilled.
3. **Were any snapshots captured late?** No leaky-late captures (all strictly pre-kickoff). One
   **benign anomaly**: BelIra T-15 was **double-captured** at 18:40:05 and 18:40:10 (5 identical rows,
   different snapshot_ts) from brief dual supervisor-instance overlap during the relaunch. Deduped for
   scoring; zero leakage impact.
4. **How many valid frozen predictions exist?** **372 rows** (35 matches), **all valid_pre_kickoff**
   (snapshot ≤ prediction < kickoff).
5. **How many are actually scorable?** **15** model-snapshot predictions for **1 match** — Belgium–Iran
   (the only predicted-upcoming fixture that finished before the deadline). Uruguay–Cape Verde kicked
   off 22:00Z and finished ~23:50Z (**after** the deadline) → its valid snapshots are **not scorable
   this session**.
6. **Did any provider request exceed the 30-credit cap?** **No** — 7/30.
7. **Did any result/event data create leakage risk?** **No.** Every snapshot is strictly pre-kickoff;
   results were used only after an explicit FINISHED status, with retrieval time recorded separately
   from event time. (The 2022 own-goal issue is an event-attribution bug in a *separate historical
   dataset*, not a live-session leak — see the data-quality report.)
8. **Did any shadow model enter an approved/runtime decision path?** **No.** M2–M5 are shadow; **B1
   remains the sole approved model**; no trading; `candidate.py` unchanged; risk gate registry-bound.
9. **Valid for descriptive scoring, or invalid?** **VALID for descriptive scoring only** — hard
   integrity passes; but **n=1 finished match → underpowered, no statistical significance.**

## Integrity verdict
- Hard integrity (`validate_shadow_integrity.py`): **all_ok = true** (no duplicate rows, all
  pre-kickoff, probs sum to 1, no-vig sums to 1, blend weights frozen).
- Warning (non-failing): duplicate-type capture for BelIra T-15 (benign, deduped).
- `pytest -q`: **132 passed**.
- Decision: session **passes** integrity → tagged `shadow-session-20260621-closed`.

## Scope guard
Descriptive only. See `shadow_session_20260621_scorecard.md` (BelIra) and
`shadow_session_20260621_data_quality.md` (2022 own-goal bug → Tier-4 BLOCK). No further work
(no odds pilot, no Tier 3/4/5) started, per instruction.
