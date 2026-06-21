# Backtest Protocol: 2018, 2022, and 2026

## Goal

Estimate how well the project would have forecast World Cup matches **using only the
information that existed at each decision time**.

## Offline pre-match evaluation

```text
2018: train through 2017 -> predict 2018 group matches
2022: train through 2021 -> predict 2022 group matches
2026 R1: train through 2025 -> predict 2026 Matchday 1, locked
```

Do not use a tournament's later group scores, post-match xG, updated rankings, or closing
prices obtained after kickoff to predict its earlier matches.

## Event-driven replay

For in-play and after-game updates, replay each tournament in chronological order:

1. Load only pre-kickoff data.
2. Generate and store a prediction snapshot.
3. During a match, reveal only events whose timestamps are no later than the simulated
   decision time.
4. After the final whistle, update Elo and group/third-place state.
5. Recompute remaining forecasts.
6. Compare prediction and execution decisions against the market snapshot available at
   the same simulated timestamp.

## Metrics

```text
Pre-match: RPS, 3-way log loss, draw Brier score, draw calibration error
In-play: time-indexed log loss/RPS, calibration by minute, score-state slices
Trading: realized P&L only as a secondary measure; CLV, fees, slippage, fills,
         maximum drawdown, and outcome-independent decision quality are required
```

A model can improve P&L by luck over a short tournament. It must demonstrate stable
probability quality before it is promoted.
