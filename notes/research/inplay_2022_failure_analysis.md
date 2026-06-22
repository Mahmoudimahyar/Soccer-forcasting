# In-Play 2022 Failure Analysis (research-only)

On the LOGO out-of-fold predictions of the leader (M2 remaining-time Poisson), 858 rows / 48 matches.

## Overconfidence
- **85/858 rows (~10%)** were predicted with max-class confidence > 0.70 yet **wrong**. These
  concentrate in mid-game level-or-one-goal states where a late swing reversed the outcome — the
  transparent Poisson cannot anticipate momentum/quality shifts (no shots/xG features).

## Draw-state failures
- On rows whose match ended in a **draw**, mean predicted p(draw) was only **0.476** — draws remain
  under-weighted (the structural draw-underconfidence also seen in pre-match work). Draw is the
  hardest class; the model leans to the leading/stronger side.

## Late-game vs ordinary
- Late game (≥76'): mean RPS **0.072** vs overall **0.155** — the model is sharp late (score largely
  decides the result), as expected. Early/level states are where most error lives.

## Event-triggered states
- Post-substitution rows: mean RPS **0.124** (better than overall, since subs cluster late). No
  evidence the model captures a substitution *impact* signal — subs are only counts, with no player
  quality/position (lineups absent), so "goal-after-substitution" effects can't be modeled here.

## Red-card states
- Only **4 rows** have a red-card imbalance and **7** `red_within_10` positives in the whole dataset.
  Any red-card claim would be anecdotal — **not analyzable** on 2022 group stage.

## Evidence that sparse features don't support some claims
- The next-goal hazard (M3) does **not** beat the base rate → with goals/cards/subs only (no
  shots/xG/possession), short-horizon next-goal timing is essentially unlearnable. This is a
  data-feature limitation, not a modeling-effort one.

## Takeaway
M2/M5 are reasonable W/D/L baselines but overconfident in volatile mid-game states and weak on draws;
next-event targets need richer features. None is suitable for live use from one tournament.
