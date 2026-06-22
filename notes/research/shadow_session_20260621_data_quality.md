# Shadow Session 2026-06-21 — Data Quality Audit

## 1. Live shadow integrity — PASS (with one benign warning)
- `validate_shadow_integrity.py` → **all_ok = true**: no duplicate rows, every snapshot strictly
  pre-kickoff, 1X2 probs sum to 1, market no-vig sums to 1, blend weights frozen (M3/M4/M5 = exact
  0.75/0.50/0.25 mixes of the same-snapshot M1/M2).
- **Warning (non-failing): duplicate-type capture.** Belgium–Iran T-15 was captured twice
  (18:40:05Z and 18:40:10Z) — 5 identical M1–M5 rows at two snapshot timestamps. **Cause:** brief
  overlap of two supervisor instances during the troubled relaunch (the dead nohup process and the
  harness-managed relaunch both fired in the 18:40 window). **Impact:** none — both captures are
  strictly pre-kickoff and identical; deduped (keep earliest) for scoring. A new check
  `check_no_duplicate_type_per_match` + test were added to detect this going forward.

## 2. 2022 event-replay reconciliation anomaly — CLASSIFIED: OWN GOAL
The replay-quality report flagged 47/48 goal reconciliation. The unresolved match is:
- **Fixture 855767 — Canada 1-2 Morocco (Group Stage 3).** Events: 4' Ziyech (Morocco), 23' En-Nesyri
  (Morocco), **40' N. Aguerd "Own Goal", `team`=Canada**.
- **Classification: OWN_GOAL event-attribution convention mismatch.** API-Football records an Own Goal
  with the **`team` field set to the BENEFITING team** (here Canada, which is credited the goal). Our
  reconciliation / `state_from_events` logic **assumes `team` is the scoring player's team and flips
  own goals to the opponent**, so it credited Morocco a 3rd goal → event-count 0-3 vs official 1-2.
- **Not VAR, not provider disagreement, not event-time mismatch** — it is purely the own-goal
  attribution convention in our code.

### Required fix (NOT applied — audit only)
In `state_from_events` (and the replay-quality reconciliation), for `detail == "Own Goal"` credit the
goal to **`team` as given** (do not flip to the opponent). After fixing, re-run reconciliation; expect
48/48. Update `docs/EVENT_RECONCILIATION_POLICY.md` to record the own-goal convention.

### Scope + block
- Affects: the **2022 event-replay dataset** for matches containing own goals (intermediate state +
  goal reconciliation). Does **not** affect the live shadow session (pre-match odds, no events) or the
  Belgium–Iran scorecard (0-0, no own goals).
- **STATUS: the 2022 event-replay dataset is BLOCKED for Tier-4 in-play / next-event model training
  until the own-goal handling is fixed and the reconciliation policy is updated** (per instruction).

## 3. Missingness summary (this session)
- Snapshot coverage: BelIra captured T-15 + final (baseline/T-90 MISSED_UNRECOVERABLE — session began
  after its T-90; not backfilled). UruCap captured all four. NewEgy baseline+T-90. 31 later fixtures:
  baseline only (their T-90/T-15 windows fall after the session). No fabricated/backfilled snapshots.
- Results: 38 finalized via football-data (FINISHED-gated). Predicted-upcoming results unavailable for
  all but BelIra within the window.

## 4. Governance confirmation
Live trading disabled (`KALSHI_ENABLE_LIVE_TRADING=false`); B1 sole approved model; M2–M5 shadow; no
model entered a runtime/decision path; `candidate.py`, trading, risk, providers, `.env`, approved-model
governance all unchanged.
