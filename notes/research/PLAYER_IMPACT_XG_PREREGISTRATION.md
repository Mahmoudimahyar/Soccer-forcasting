# Player-Impact & xG Fusion — PREREGISTRATION (frozen before results; 2026-06-26)
research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

## 1. Evaluation population
- PRIMARY: senior men's INTERNATIONAL matches only (WC2018/2022, Euro2020/2024, Copa2024, AFCON2023, AsianCup2023).
- Club matches: AUXILIARY-only (player-history priors); NEVER silently pooled with international evaluation rows.
- No completed 2026 World Cup matches used for selection/calibration/feature-selection/promotion.

## 2. Primary outer evaluation
Leave-one-international-competition-out; temporal causality enforced (priors use only pre-decision appearances);
match-level paired bootstrap; NO random row-level splits.

## 3. Model families (transparent, regularized; NO NN/transformer/LLM; no open-ended hyperparameter search)
- W2 reference: existing remaining-time Poisson.
- P1: W2 + pre-match starting-XI player-impact difference + uncertainty.
- P2: P1 + current on-pitch player-impact difference.
- P3: P2 + substitution-delta history.
- P4: P3 + team-state (score_diff, remaining, player_count_diff, card_diff, subs_used).
- Next-goal: N0 base-rate; N1 time/score/card/sub hazard; N2 +on-pitch player-impact; N3 +substitution delta.
- Discipline: C0 base-rate sending-off; C1 +player/team discipline history (only if exposure + >=150 positives).
- xG fusion (matched StatsBomb intl subset): X0 = W2 on matched subset; X1 = W2 + xG event-state;
  X2 = W2 + player-impact state; X3 = W2 + player-impact + xG event-state.

## 4. Primary metrics
RPS; three-way log loss; draw Brier; calibration slope/intercept; ECE; match-level paired bootstrap.

## 5. Success rule for RESEARCH-candidate review (all required)
- lower mean RPS than W2; improvement direction consistent in >=4 international outer folds;
- paired match-level bootstrap 95% interval excludes zero OR is clearly materially favorable;
- no meaningful calibration degradation; not reliant on a single competition; not club-only.

## 6. No-promotion rule
Even a passing result stays research-only. NO runtime/shadow/paper/Kalshi/trading change in this run.
B1 remains sole runtime; M1-M5 + frozen M2 untouched. Do not change preregistered choices after seeing results.

## Honest outcomes (the run SUCCEEDS by producing one of these)
1. player-impact/sub-delta beats W2 robustly; 2. fails robustly + rejected; 3. xG fusion improves the strictly
limited-sample eval; 4. xG fusion fails + rejected; 5. data quality prevents a valid conclusion (documented precisely).
