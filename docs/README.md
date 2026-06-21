# Documentation Index

This directory explains the reasoning behind the World Cup Draw Model Lab.
The project is intentionally built as a probability-and-testing framework, not as a pile of fixed heuristics.

Read in this order:

1. [`PROBABILITY_AND_STATISTICAL_REASONING.md`](PROBABILITY_AND_STATISTICAL_REASONING.md) — the mathematical foundation.
2. [`MODEL_ARCHITECTURE.md`](MODEL_ARCHITECTURE.md) — why the model is layered and how the pieces fit.
3. [`RISK_AND_UNCERTAINTY.md`](RISK_AND_UNCERTAINTY.md) — how standard deviation, entropy, confidence, probability intervals, and bet-risk are computed.
4. [`DATA_CONTRACTS_AND_LEAKAGE.md`](DATA_CONTRACTS_AND_LEAKAGE.md) — timestamp discipline and input schemas.
5. [`ABLATION_AND_TESTING_PLAN.md`](ABLATION_AND_TESTING_PLAN.md) — how every idea must be tested before being trusted.
6. [`BETTING_RISK_POLICY.md`](BETTING_RISK_POLICY.md) — how to separate prediction from betting edge.
7. [`MODEL_CARD.md`](MODEL_CARD.md) — what the system is for, what it is not for, and known limitations.
8. [`BACKTEST_PROTOCOL_2018_2022_2026.md`](BACKTEST_PROTOCOL_2018_2022_2026.md) — frozen historical and event-time evaluation.
9. [`AUTORESEARCH_GOVERNANCE.md`](AUTORESEARCH_GOVERNANCE.md) — Claude Code research boundaries and promotion rules.
10. [`LIVE_TRADING_ARCHITECTURE.md`](LIVE_TRADING_ARCHITECTURE.md) — paper/demo/live execution separation and Kalshi safeguards.
11. [`DATA_SOURCE_GOVERNANCE.md`](DATA_SOURCE_GOVERNANCE.md) — API approval and compliant scraping controls.
12. [`CLAUDE_CODE_BOOTSTRAP_PROMPT.md`](CLAUDE_CODE_BOOTSTRAP_PROMPT.md) — the first prompt to give Claude Code.

The short version: a draw prediction is not just a point estimate. Every prediction now carries uncertainty columns:

- `outcome_sd_a`, `outcome_sd_draw`, `outcome_sd_b`
- `prob_se_a`, `prob_se_draw`, `prob_se_b`
- `prob_ci_low_*`, `prob_ci_high_*`
- `prediction_entropy`
- `confidence_score`
- `risk_band`
- for betting scans: `draw_bet_ev_per_unit`, `draw_bet_sd_per_unit`, `draw_bet_sharpe_like`


## Live after-game updates

The model is designed to update **after each completed game**. Use:

```bash
wcdrawlab predict-live --matches data/live/current_matches.csv --output outputs/live
```

before games, and after every final score:

```bash
wcdrawlab update-after-match \
  --matches data/live/current_matches.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1 \
  --current-matches data/live/current_matches.csv \
  --output outputs/live
```

See `docs/PREDICTION_TARGETS_AND_UPDATE_CADENCE.md` and `docs/AFTER_GAME_UPDATE_WORKFLOW.md` for the complete explanation.
