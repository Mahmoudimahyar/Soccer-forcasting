# Paid Source Activation and Historical Event Coverage V1 — Completion

research_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true ·
KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Worktree `C:/Users/Mahyar/worldcup-paid-source-activation`, branch `paid-source-activation-v1`.

## Active-collector isolation result (verified)
Collector untouched: main checkout `worldcup_draw_model_lab_FINAL`, `v1-5-prospective-operations` @ **dc73318**,
tracked-clean, task **Ready**, heartbeat advancing (…05:58Z), odds budget ledger untouched. `git diff
dc73318..HEAD` = **28 Added, 0 Modified** — no collector code/scheduler/forecast/ledger changed. 6 tests pass.
No key revealed (only SET/MISSING reported). All raw API data + processed outputs gitignored (0 tracked).
B1 remains the sole approved runtime model; M1-M5 + frozen in-play M2 unchanged.

## API-Football real coverage findings (27 requests, Pro 7,500/day)
available_verified for 5 international tournaments + UCL: fixtures, timestamps, final scores, event timelines
(goals/cards/subs/VAR with player.id + minute), **lineups + benches + player IDs + positions + formation**,
team shots. available_partial: VAR/own-goals/red cards (rare per fixture), **xG (Euro2024 yes, WC2022 no)**.
**unavailable_verified: shot locations (xy)** — team-level stats only.

## Acceptance status
**accepted_for_limited_historical_research** — fixtures/lineups/subs/player-IDs/cards/timestamps verified;
LIMITS: xG partial, shot-locations unavailable, red/2Y counts pending backfill, redistribution/commercial/
model-training rights unknown_requires_vendor_confirmation.

## Request counts & budget use
- API-Football: Phase 1 = 27/30; Phase 3 backfill = 245/300 (no auth/entitlement error). Pro daily = 7,500.
- Odds API: Phase 4 = 20/30 credits (2 historical snapshots); account `x-requests-remaining` 13,055 after —
  the collector's quota + ledger untouched. No live loop run.

## Historical pilot corpus
**120 finished international matches** (WC2022 + Euro2024 + Copa2024 + AFCON2023 + AsianCup2023), append-only
gitignored, manifested. Quality: **120/120 with events + lineups + player IDs; duplicate rate 0.0005; score
reconciliation 90% exact** (12 mismatches at ET/shootout/VAR boundaries).

## Event / lineup / substitution / card coverage (pilot)
1,890 events; 1,085 substitutions; 432 yellows; 12 reds; 3 second-yellows (**15 red-or-2Y**); 12 own goals;
302 goals. Lineups + benches + player IDs + positions on all 120.

## Odds API historical pilot outcome
**sufficient** — 6/6 predeclared WC2022 fixtures (10 bookmakers each, >=60 min pre-KO), no-vig median 1X2.
Diagnostic only; market favorites realized except the Argentina-Saudi upset; balanced games drew. No M1-M5 change.

## Model-readiness counts (observed; NOT trained)
| class | pilot | threshold | meets | reachable |
|---|---|---|---|---|
| player/substitution | 120 lineup+ID matches | 500 | no | YES (2,180 avail; quality 100%) |
| card (yellow) | 432 | n/a | — | yes |
| red/2nd-yellow | 15 | 150 | no | ~1,200-match backfill (add leagues) |
| next-goal (timestamped) | 120 / 302 goals | 500 | no | YES |
| in-play W/D/L | 90% reconcile | clean | — | yes |
| xG / shot-quality | partial / no xy | — | no | provider gap |

## Data gaps remaining
red-card VOLUME (largest backfill lift); xG partial; shot-locations unavailable; rights-in-writing; live
publication-time/latency for any future shadow use.

## Is a new provider truly still needed?
**Only for xG / shot-location / shot-quality research.** For player/substitution/card/next-goal/in-play W/D/L,
API-Football Pro (already paid) is sufficient — quality verified, thresholds reachable via bounded backfill.

## Exact next recommended sprint
"API-Football Historical Backfill to Threshold V1": bounded, budget-reserved backfill to >=500 lineup/sub +
>=500 timestamped matches (intl + major leagues), pushing red/2Y toward 150, then build leakage-safe
research datasets + baseline player/sub/card/next-goal models (still research-only, competition holdouts).

## What must remain frozen / why trading stays disabled
M1-M5, in-play M2, B1 (sole runtime), candidate.py, approved_models.yaml, collector code/task/cadence/odds
budget, and all trading/risk/Kalshi/paper code remain FROZEN. Trading stays disabled
(KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper): this sprint is historical research activation only;
no live publication-time semantics + no causal-gated shadow exist yet, so nothing here is live/trade eligible.
