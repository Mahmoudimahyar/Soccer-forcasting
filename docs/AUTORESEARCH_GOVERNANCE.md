# Autoresearch Governance

This project adapts the useful part of Karpathy's `autoresearch` pattern: a fixed
preparation/evaluation harness, a deliberately small agent-editable candidate, a stable
metric, and an experiment log. Karpathy's reference implementation separates fixed data
preparation from a single agent-editable training file and uses fixed-budget evaluation
for comparability. Our project follows the same idea, but the objective is probability
forecast quality rather than neural-network loss. citeturn674683view0

## Why the research plane is isolated

A self-improving research agent and an execution process must not share authority.
Research is allowed to fail, revert, and explore. Execution must be deterministic,
versioned, rate-limited, and governed by risk constraints. Therefore:

```text
research plane -> produces experiment evidence
human approval -> marks a model version deployable
runtime plane -> reads only approved immutable artifacts
execution plane -> can submit demo/live orders only after risk gates pass
```

No autoresearch result automatically becomes an executable strategy.

## Frozen protocol

### Data eligibility

Every feature must satisfy:

\[
feature\_available\_at \le match\_kickoff
\]

In-play features must satisfy the stricter event-time condition:

\[
feature\_available\_at \le decision\_timestamp
\]

### Historical folds

| Fold | Training data | Test data | Purpose |
|---|---|---|---|
| 2018 | Matches before 2018 | 2018 World Cup group stage | First external check |
| 2022 | Matches before 2022 | 2022 World Cup group stage | Second external check |
| 2026 R1 | Matches before 2026 | 2026 group-stage Matchday 1 | Locked contemporary check |

The 2026 Matchday 1 fold is not available for iterative tuning. It is a final drift and
transfer check. Use a separate prequential replay to evaluate after-game state updates.

### Objective

\[
J = 0.40\,RPS + 0.25\,LogLoss + 0.20\,Brier_{draw} + 0.15\,ECE_{draw}
\]

All components are minimized. A candidate is retained only when its aggregate score
improves and it does not materially degrade a holdout. The project prioritizes calibrated
probabilities because a trading/decision layer consumes probabilities, not labels.

## Promotion protocol

1. The agent writes evidence to `outputs/research/` and `notes/research/`.
2. A human reviews metrics, calibration, and diff.
3. A human tags the exact commit/model artifact as approved.
4. Only that version may be added to the runtime approval list.
5. The runtime rejects an intent whose `model_version` is not approved.

## What the agent may change

Only `src/wcdrawlab/research/candidate.py` by default. It receives a leakage-safe numeric
feature table. It cannot directly access raw goals, post-match data, API keys, runtime
settings, execution code, or trading policy.

## What the agent must not optimize

- one tournament in isolation;
- raw accuracy at the expense of calibration;
- retrospective betting ROI using stale/impossible prices;
- a live market using data published after the decision timestamp.
