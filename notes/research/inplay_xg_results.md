# Live In-Play xG Results (research-only, 2026-06-22) — StatsBomb

Data provided by **StatsBomb** (open data, non-commercial research). Tested whether **leakage-safe live
xG** improves the in-play forecast. StatsBomb open data covers two of our six in-play competitions:
**World Cup 2022** (64 matches, 1494 shots) and **Copa America 2024** (32 matches, 790 shots).

## Method
Per-shot xG joined to in-play decision rows; each team's xG accumulated **strictly before** the decision
minute (no look-ahead — unit-tested in `tests/test_xg_inplay.py`). Features: `live_xg_diff`
(home−away cumulative xG) and `xg_surprise` (xG_diff − score_diff = "deserved vs actual"). Evaluated on
leave-one-COMPETITION-out (WC2022 ↔ Copa2024), 68 mapped matches / 1213 rows.

## Result — NEGATIVE (honest)
**(1) W/D/L** (baseline score+Elo RPS 0.1845):
| added feature | RPS | dRPS vs baseline | CI | verdict |
|---|---|---|---|---|
| +live_xg_diff | 0.1859 | +0.0022 | [−0.002, +0.007] | ns |
| +xg_surprise | 0.1884 | +0.0045 | [−0.001, +0.011] | ns |
| +both | 0.1821 | −0.0015 | [−0.008, +0.005] | ns |

No live-xG feature significantly beats score+Elo. (The "+both" hint is within noise; I did **not**
keep adding features to chase significance — that would be fishing on 68 matches.)

**(2) Next-goal** (predict which team scores next): adding `live_xg_diff` made it **worse**
(log-loss 0.818 → 0.904). *Cumulative* xG correlates with being ahead, and leading teams defend, so
total xG is anti-predictive of the next scorer; the right signal would be recent attacking threat, not
season-to-date totals. The 2-fold out-of-competition next-goal transfer is also weaker than coin-flip,
so the test is underpowered regardless.

## Honest conclusion
At the **available xG scale (2 competitions, 68 matches)**, StatsBomb live xG does **not** demonstrably
improve the in-play model beyond score + time + Elo. This is the third independent confirmation of the
session's pattern: **the simple in-play state (score / time / Elo) is hard to beat; richer features
(player plane, live xG) are largely redundant or transfer poorly at this data scale.** The validated
model improvement this session remains **M2fit_temp** (data-fit anchor + temperature scaling).

## What would change the verdict (not fishing — pre-registered)
- More xG-covered competitions (StatsBomb adds tournaments over time) → real LOGO power.
- A *recent-window* xG-rate feature for next-goal (theory: momentum, not cumulative) — to be tested only
  with enough competitions to avoid 2-fold overfit.
- Infrastructure (`src/wcdrawlab/research/xg_inplay.py`, `scripts/fetch_statsbomb_xg.py`,
  `eval_inplay_xg.py`) is reusable + leakage-safe for when that data exists.
