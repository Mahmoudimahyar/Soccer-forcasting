# Program Backlog (priority-ordered)

Status: ✅ done · 🔓 unblocked-feasible · ⛔ externally blocked. Only 🔓 items are actionable now.

## Phase A — consolidate (✅)
- ✅ Program control files + `PROGRAM_CURRENT_TRUTH.md`.

## Phase B — data-source expansion (mostly ✅; rest 🔓 small / ⛔)
- 🔓 Re-verify API-Football direct (1 safe call) + read-only historical adapter (2022–2024) + dry-run.
- ✅ football-data.org / Odds API / Open-Meteo audited & working.
- ⛔ Live 2026 API-Football events/lineups (paid Pro).

## Phase C — multi-competition event program (design 🔓; ingest ⛔)
- 🔓 Canonical multi-competition event schema (design, absorbs WC/continental/national).
- ⛔ Actual multi-competition ingestion (needs approved source / quota authorization).

## Phase D — research datasets & validation (🔓 on existing 2022 data)
- 🔓 Split in-play data into data products (pre-match / team-state / event-horizon / card / sub-state /
  context / qualification) from existing 2022 data.
- 🔓 Reusable evaluation framework module (+ tests).
- ⛔ Player/on-pitch product (needs lineups).

## Phase E — model research (✅ in-play ladder; rest ⛔)
- ✅ In-play M0–M5 evaluated (sprint 1).
- ⛔ Player-state, card-hazard, richer next-event (sparse/blocked data).
- 🔓 Model registry doc (approved vs experimental).

## Phase F — shadow-readiness & durable collection (🔓 docs; components ✅)
- ✅ Durable restart-safe collector (supervisor + resume + integrity + ledger).
- 🔓 Scheduler instructions (Windows Task Scheduler + cron) + SHADOW-CANDIDATE criteria doc.
- ⛔ Declaring any model SHADOW-CANDIDATE (needs ≥2 independent competition/time holdouts → blocked).

## Phase G — finalize or block (🔓)
- 🔓 Completion or external-blockers report + commit + tag.

## Terminal
After all 🔓 items: remaining work is ⛔ (multi-competition data, player plane, shadow-ready) →
tag `worldcup-predictor-v1-blocked`.
