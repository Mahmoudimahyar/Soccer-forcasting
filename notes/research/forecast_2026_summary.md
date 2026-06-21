# 2026 World Cup Group Stage — Forecast Snapshot (2026-06-20)

Script: `scripts/forecast_2026.py`. Model: **B7 calibrated ensemble** (Elo + Dixon-Coles +
logit, Platt draw recalibration); Elo-only shown alongside. Trained on all played WC group
matches available now (1998–2022 + completed 2026 through 2026-06-18). Each match uses only
information available before its kickoff. **Not betting-grade** — no real market odds yet.

Files: `outputs/research/forecasts/forecast_2026_md2_md3.csv` (per-match probs + uncertainty),
`outputs/research/forecasts/advancement_2026.csv` (per-team, 20k Monte-Carlo sims with
best-third qualification).

## State of play (data snapshot)
- Matchday 1: complete (24 matches). Matchday 2: 4 of 24 played; **20 remaining**.
- Matchday 3: 24 remaining. MD3 forecasts are **provisional** — they assume current standings
  and will sharpen after MD2 results (re-run the after-game update).

## Matchday 2 forecast (the immediate objective) — % [win_a / draw / win_b]
| Group | Match | A% | D% | B% | Risk |
|---|---|---|---|---|---|
| C | Brazil vs Haiti | 82 | 13 | 5 | low |
| C | Scotland vs Morocco | 18 | 27 | 55 | high |
| D | Turkey vs Paraguay | 45 | 29 | 25 | high |
| D | United States vs Australia | 42 | 31 | 27 | high |
| E | Ecuador vs Curaçao | 82 | 14 | 4 | low |
| E | Germany vs Ivory Coast | 53 | 31 | 17 | high |
| F | Netherlands vs Sweden | 63 | 19 | 18 | high |
| F | Tunisia vs Japan | 9 | 15 | 76 | medium |
| G | Belgium vs Iran | 50 | 26 | 24 | high |
| G | New Zealand vs Egypt | 20 | 25 | 55 | high |
| H | Spain vs Saudi Arabia | 88 | 9 | 3 | low |
| H | Uruguay vs Cape Verde | 69 | 20 | 11 | medium |
| I | France vs Iraq | 81 | 14 | 5 | low |
| I | Norway vs Senegal | 47 | 31 | 22 | high |
| J | Argentina vs Austria | 67 | 21 | 12 | high |
| J | Jordan vs Algeria | 17 | 26 | 57 | high |
| K | Colombia vs Congo DR | 72 | 18 | 9 | medium |
| K | Portugal vs Uzbekistan | 67 | 21 | 12 | high |
| L | England vs Ghana | 85 | 11 | 4 | low |
| L | Panama vs Croatia | 17 | 26 | 57 | high |

(Groups A and B MD2 are already played and excluded.)

## Advancement probability (top-2 + 8 best thirds; 20k sims)
Near-locks: Mexico, Canada, Switzerland, Germany, France, Argentina, England ≈ 100%.
Strong: USA 99%, Norway 99%, Colombia 99%, Ivory Coast 98%, Sweden 98%, Brazil 96%, Spain 96%,
Australia 96%, Austria 95%, Korea Republic 94%, Netherlands 93%, Japan 93%, Morocco 92%, Belgium 90%.
Live races (best-third sensitive): Group G (Egypt 73 / Iran 66 / NZ 34), Group H (Uruguay 76 /
Cape Verde 46 / Saudi 45), Group K (Portugal 84 / Congo DR 46 / Uzbekistan 33). Full table in
`advancement_2026.csv`.

## Uncertainty
Each match carries a draw standard error + CI, prediction entropy, confidence score and a
risk band (low/medium/high). "high" bands flag genuine toss-ups where the prediction should be
treated as weak (e.g. Belgium–Iran 50/26/24, USA–Australia 42/31/27).

## Caveats (read before trusting any number)
1. **Elo-grade, not market-grade.** No real odds exist; these are calibrated strength
   forecasts. Per `baseline_evaluation.md`, no free-data model robustly beats Elo + market,
   and the market baseline isn't built yet.
2. **2026 MD1 showed a draw spike** the historical models under-predict; draw probabilities
   here may be modestly low. Reflected in the locked-fold draw-calibration (0.21).
3. **MD3 is provisional** — re-run after each MD2 result via the after-game update so Elo,
   standings, and best-third safety refresh.
4. Source latency: martj42 results lag the calendar ~2 days; confirm scores before relying on
   the freshest fixtures.
