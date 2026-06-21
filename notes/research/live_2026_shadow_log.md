# Live-2026 Shadow Evaluation Log

Running log of the prospective shadow experiment. Predictions are **immutable after kickoff**;
nothing is promoted; B1 stays the only approved runtime model.

## Frozen model set (fixed for the entire evaluation)
- **M1_B1** — approved Elo (ternary, r=0.4). [approval_status=approved]
- **M2_market** — no-vig market consensus. [shadow]
- **M3_75_25** — 0.75·B1 + 0.25·market. [shadow]
- **M4_50_50** — 0.50·B1 + 0.50·market. [shadow]
- **M5_25_75** — 0.25·B1 + 0.75·market. [shadow]
Weights/features/calibration/thresholds/uncertainty rules are FROZEN. They will not change based on
any 2026 result.

## Runs
### 2026-06-21T18:06Z — freeze #1
- Live odds snapshot captured (h2h/us): 36 events, 1 credit (quota 13,099 remaining).
- Froze pre-kickoff predictions for **35 upcoming matches** → **171 rows** (M1–M5 where market
  present; M1-only otherwise), `outputs/research/live_2026_shadow_predictions.csv`.
- Scoring: 0 finished yet (all upcoming) — metrics populate as MD2/MD3 complete.
- Example (Argentina vs Austria): B1 0.713/0.187/0.100 vs market 0.623/0.232/0.145 → blends
  interpolate; B1 is sharper on the favorite.

## How to continue (recurring)
- Capture snapshots near each match: `python scripts/live_2026_shadow.py freeze` after refreshing a
  live odds snapshot (the collector reuses the latest raw snapshot; schedule it at T-24h / T-90m /
  T-15m / final pre-kickoff).
- After matches finish (refresh results): `python scripts/live_2026_shadow.py score` →
  `live_2026_shadow_metrics.csv` + `..._calibration.csv`.
- Permitted post-match dynamic-state updates only: internal Elo, standings, group draw/goals state,
  third-place safety, advancement probs, rest/fatigue. Core architecture stays frozen.
