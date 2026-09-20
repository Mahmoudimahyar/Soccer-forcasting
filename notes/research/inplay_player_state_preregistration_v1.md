# In-Play Player-State Preregistration V1 (frozen before evaluation)
research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

## Hard rules
- NO completed 2026 World Cup matches used for model selection or tuning (corpus is 2018-2024 + 2023-24 club).
- Primary evaluation: INTERNATIONAL data only; leave-one-competition-out (LOCO) outer validation;
  match-level bootstrap CIs; ALL model design + hyperparameters + calibration fit INSIDE training competitions;
  NO random row-level splits.
- Club data: AUXILIARY-only; used only in a SEPARATELY LABELED club->international transfer experiment
  (JOB9), evaluated only on held-out INTERNATIONAL competitions; never silently pooled.
- Causal: features at decision minute t use only events with elapsed<=t; regulation-only targets exclude
  ET/shootout; own-goal beneficiary semantics; no final-score/later-sub leak.

## Preregistered model families (NO NN/transformer/LLM; no hyperparameter fishing; no unregistered variants)
### W/D/L (regulation outcome from in-play state)
- W0 static base-rate (prematch-style prior carried through).
- W1 score-diff empirical.
- W2 remaining-time Poisson (parameter-free m2, base=1.35; reimplemented, frozen M2 NOT imported/modified).
- W3 W2-context + multinomial logistic on [score_diff, card_diff, sending-off_diff, subs_diff,
  player_count_diff, remaining].
- W4 W3 + cautious lineup-continuity proxies [starting-XI size, ... ] (continuity coverage flagged).
### Next-goal (P regulation goal in next 15 min)
- N0 base-rate; N1 regularized logistic hazard [minute, score_diff, player_count_diff, card_diff, subs];
  N2 N1 + continuity (only if coverage passes — it is ~100%).
### Discipline
- C0 yellow-card state base-rate. C1 sending-off hazard ONLY IF >=150 positive events after the extension.

## Metrics (preregistered)
W/D/L: RPS, 3-way log loss, draw Brier, calibration slope/intercept, ECE, reliability by minute/score/
player-count, paired match-level bootstrap CIs.
Next-goal: Brier, log loss, calibration, base-rate comparison, minute/score/card-state, class balance.
Discipline: base-rate comparison, Brier, calibration, positive-event count, CI, explicit sufficiency decision.

## Claims discipline
No significance from correlated state rows (bootstrap at MATCH level only). No player-specific causal claims.
No model promoted to runtime. B1 remains sole runtime; M1-M5 + frozen M2 unchanged; trading disabled.
