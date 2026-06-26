# Paid Source Model Readiness Update (Phase 6)
research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. Counts are observed (120-match pilot).

| model class | data status | threshold | next step | provider |
|---|---|---|---|---|
| player / substitution | UNBLOCKED (clean; 120/120) | 500 matches | bounded backfill to 500 | API-Football (paid, have) |
| card (yellow) | UNBLOCKED (432 in pilot) | n/a | use pilot + backfill | API-Football |
| red / second-yellow | PARTIAL (15/120) | 150 examples | ~1,200-match backfill (add leagues) | API-Football |
| next-goal (timestamped) | UNBLOCKED (120/120, 302 goals) | 500 matches | bounded backfill to 500 | API-Football |
| in-play W/D/L | UNBLOCKED (90% reconcile) | clean timelines | backfill + leakage-safe split | API-Football |
| xG / shot-quality | BLOCKED (partial xG, no xy) | per-shot xG+loc | richer provider / xG add-on | Opta/StatsBomb (external) |
| any live/trading model | FROZEN / out of scope | n/a | none (KALSHI_ENABLE_LIVE_TRADING=false) | n/a |

Frozen + unchanged: M1-M5, in-play M2, B1 (sole runtime), candidate.py, approved_models.yaml, trading/risk/Kalshi.
No model was trained or promoted in this sprint.
