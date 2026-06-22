> **SUPERSEDED 2026-06-21 (same day):** this report's 'fully blocked' conclusion was PREMATURE. API-Football's free tier covers Euro/Copa/AFCON/Nations-League/friendlies (2022-2024), so the multi-competition in-play plane is UNBLOCKED. See `inplay_multicompetition_results.md` + `RESUME_NEXT_TASK.md`. Genuinely-blocked items now: player plane (lineups/xG -> paid API-Football Pro) and more competitions (free-tier daily quota, rate-paced).

# World Cup Predictor V1 — External Blockers Report

**Terminal state: EXTERNALLY BLOCKED** (not complete). All independent, lawful, scientifically valid
work is done; every remaining V1 item requires your external action. Tag: `worldcup-predictor-v1-blocked`.
Safety intact: B1 sole approved model; paper-only; no protected files changed; `pytest -q` = 159 passed.

## Completed (unblocked) work
- **Control plane:** PROGRAM_STATE/BACKLOG/WORK_LOG/BLOCKERS/DoD + PROGRAM_CURRENT_TRUTH.
- **Data/source plane:** providers audited; API-Football direct re-verified (Free, 2022–2024 only);
  read-only **season-gated historical adapter** (dry-run, fail-closed) + tests; provenance/reconciliation
  contracts; durable collector design.
- **Pre-match plane:** B1 reproducible; B0–B7 + market shadow tested; nothing beats B1 → none promoted.
- **In-play plane:** validated 2022 replay; canonical state dataset (858 rows); M0–M5 + honest LOGO
  evaluation; reusable **evaluation framework** (`inplay_eval.py`) + **data products** (5 available,
  3 blocked); **multi-competition event schema** (design).
- **Shadow plane:** restart-safe collector + integrity + ledger + closure; **scheduler instructions**
  (Windows Task Scheduler + cron) + **SHADOW-CANDIDATE criteria**.
- **Registries:** model registry (B1 approved; rest experimental) + data registry (current truth).

## Model / data readiness
- Runtime-approved: **B1 only.** Shadow-ready: **none.** In-play research leaders M2/M5 lack a 2nd
  independent competition holdout. Next-goal hazard fails vs base rate (no xG/shots/lineups).

## Remaining blockers (all require your action)
| id | blocker | account/approval needed | expected value | exact next task once resolved |
|---|---|---|---|---|
| BLK-1 | multi-competition event volume | approve StatsBomb open (free, NC sign-off) **or** authorize multi-day API-Football quota | **high** — only path to player/card/next-event models | ingest via the schema; re-run in-play ladder with leave-one-competition-out |
| BLK-2 | xG / shots / lineups / player IDs | API-Football **Pro (~$25–30/mo)** or paid xG feed | **high** — fixes failed next-goal hazard + enables player/tactical plane | add shots/xG/lineup columns; richer M3/M4 |
| BLK-3 | live 2026 events/lineups | API-Football Pro upgrade | med — live in-play 2026 | wire live event ingestion behind interface |
| BLK-4 | pre-2020 dev-fold odds | none cheap (no legal source) | med — would let a market blend clear promotion | accept market as shadow-only |
| BLK-5 | rare next-event volume (red cards) | resolved by BLK-1 | low-med | red-card hazard once positives sufficient |

## Shadow-ready? Runtime-approved? Live trading?
- Shadow-ready: **no model.** Runtime-approved: **B1 only.**
- **Live trading remains disabled** (`KALSHI_ENABLE_LIVE_TRADING=false`, paper) — no model is even
  shadow-ready, Kalshi credentials are absent, and promotion needs separate human approval.

## Recommended single next action
**Approve BLK-1 (StatsBomb open data sign-off)** — free, unlocks multi-competition events + lineups +
xG for the player/in-play planes, which everything else depends on. Then BLK-2 (API-Football Pro) for
live 2026. Until then the program is correctly paused, not failed.
