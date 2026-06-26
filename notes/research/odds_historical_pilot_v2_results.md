# Odds API Historical Pilot V2 — Results (Phase 4)

research_only / **DIAGNOSTIC ONLY** / not_runtime_approved / not_trade_eligible / not_live_eligible. No model
trained/tuned/promoted; M1-M5 untouched. Selection was PREDECLARED before retrieval
(`odds_historical_pilot_v2_protocol.md`). Coverage CSV (gitignored): `data/processed/odds_historical_pilot_v2_coverage.csv`.

## Budget
**20 of 30 credits** used (2 historical snapshots, region=eu, market=h2h, 10 credits each). Odds API
account `x-requests-remaining` = 13,055 after the pilot -> the active collector's quota is unaffected. The
collector's odds-budget ledger was NOT touched; no live loop was run. Key never printed.

## Verdict: **sufficient** (6/6 predeclared fixtures valid: >=3 bookmakers, all three 1X2 outcomes, >=60 min pre-KO)

| match | declared | realized | bookmakers | min before KO | p(H) | p(D) | p(A) | no-vig median |
|---|---|---|---|---|---|---|---|---|
| Argentina v Saudi Arabia | favorite | AWAY (upset) | 10 | 124 | 0.863 | 0.101 | 0.036 | favorite missed the shock |
| France v Australia | favorite | home | 10 | 484 | 0.757 | 0.165 | 0.078 | favorite correct |
| Denmark v Tunisia | balanced | DRAW | 10 | 304 | 0.599 | 0.253 | 0.148 | drew vs lean-Denmark |
| Mexico v Poland | balanced | DRAW | 10 | 544 | 0.391 | 0.314 | 0.296 | flattest dist; drew |
| Brazil v Serbia | favorite | home | 10 | 3184+ | 0.661 | 0.212 | 0.128 | favorite correct |
| Uruguay v South Korea | balanced | DRAW | 10 | 3184+ | 0.546 | 0.271 | 0.183 | drew vs lean-Uruguay |

## Observations (diagnostic, no inference for model promotion)
- Method works end-to-end: historical snapshot -> per-bookmaker no-vig -> median across 10 bookmakers ->
  calibrated-looking 1X2 distributions, with source timestamps preserved.
- Market favorites realized in all favorite fixtures EXCEPT the historic Argentina-Saudi upset; the most
  balanced fixture (Mexico-Poland, pH 0.39) drew. Consistent with market being well-calibrated but not clairvoyant.
- The first snapshot (2022-11-22T08:00Z) already contained odds for the 11-24 fixtures (bookmakers post days
  ahead) -> the second snapshot was redundant; ONE snapshot (10 credits) would have sufficed. Recorded for
  future budget efficiency.

## Boundary
Diagnostic only. This pilot does NOT feed M1-M5, does NOT alter the collector, and makes no market-edge claim.
The active collector remains the sole live-odds path.
