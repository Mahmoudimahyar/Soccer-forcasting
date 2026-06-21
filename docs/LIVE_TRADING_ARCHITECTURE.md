# Live Prediction and Guarded Kalshi Execution Architecture

## Separation of concerns

```text
[Data providers] -> [Feature/event store] -> [Prediction engines] -> [Decision engine]
       |                     |                       |                    |
       |                     |                       |                    v
       |                     |                       |             [Risk gate]
       |                     |                       |                    |
       |                     |                       |                    v
       |                     |                       |       [Paper / Demo / Live gateway]
       v                     v                       v                    v
   raw snapshots         replay data          versioned forecasts      audit log
```

The data layer is read-only. The prediction layer outputs probabilities and uncertainty.
The decision layer creates a `TradeIntent` only after an explicit market mapping.
The risk gate decides whether the intent is allowed. The Kalshi client submits nothing
until its environment and confirmation switches are deliberately armed.

Kalshi exposes REST and WebSocket APIs for real-time market data and trade execution,
with separate demo and production environments. Credentials are environment-specific.
Use the demo environment first. citeturn674683view1turn510325view0

## Required modes

| Mode | What happens |
|---|---|
| `paper` | Simulate decision and fills locally. No Kalshi credentials required. |
| `demo` | Use Kalshi demo credentials and demo endpoints. Orders may be submitted to demo only. |
| `live` | Production endpoint. Requires explicit external arming, risk approval, and a human-approved model version. |

The default is `paper`. `demo` is required before `live`.

## No automatic market mapping

A football model predicts events such as `Canada win`, `draw`, or `Qatar win`. Kalshi
orders operate on an exchange market ticker and V2 single-book `bid`/`ask` side. The
system must never guess how a football outcome maps to an order. The user maintains a
versioned `data/live/market_map.csv` containing the match ID, Kalshi event/market ticker,
outcome label, order-book side, and expiry. Every mapping is manually reviewed.

This guard is critical because a wrong mapping can trade the opposite outcome.

## Order gate

A `TradeIntent` must satisfy all of these before it reaches a gateway:

```text
- model version is human-approved
- market is open and quote is fresh
- model prediction is fresh
- edge is positive after lower confidence bound, not only point estimate
- spread is within cap
- per-order, event-exposure, open-order, and daily-loss caps pass
- explicit market mapping exists
- live mode is armed outside Claude Code
```

The trade engine uses **limit orders**. Kalshi's V2 endpoint accepts bid/ask order sides
and fixed-point dollar prices; its API recommends client order IDs to prevent accidental
duplicate orders. citeturn917783view1turn409936view1

## In-play model

The initial in-play benchmark conditions regulation-time 1X2 probabilities on:

```text
minute, current score, red cards, optional xG, and pregame goal rates
```

Remaining goals are modeled with remaining-time Poisson hazards. Score state changes
attack intensity; red cards and xG surprise adjust hazards modestly. This is a
transparent starting point, not a claim of production-grade alpha. It must be calibrated
using historical event-time data before it can influence demo/live execution.

## Kalshi credentials

Keep these outside version control:

```text
KALSHI_API_KEY_ID
KALSHI_PRIVATE_KEY_PATH
KALSHI_ENABLE_LIVE_TRADING
KALSHI_LIVE_TRADING_ACK
```

Kalshi authenticates requests with an API key ID, millisecond timestamp, and an
RSA-PSS/SHA-256 signature over `timestamp + HTTP method + request path`. citeturn917783view0

## WebSocket use

Use the Kalshi WebSocket for market/order-book/fill updates, with reconnect backoff and
raw-message snapshots. Kalshi documents channels for ticker updates, order-book deltas,
trades, market lifecycle, and fill notifications. citeturn917783view2

## Kill switches

The service must stop submitting new orders when any of these occur:

```text
stale or missing live-data feed
market closed/paused
provider schema failure
risk cap breach
daily loss limit reached
unknown model version
clock drift / auth failures
repeated API errors
manual kill-switch file exists
```

## In-play position changes: buy, add, reduce, or hold

The runtime handles an in-play update as a **target-position** problem, not a repeated
"place a bet" problem:

```text
1. Ingest live event state and fresh exchange quote.
2. Recompute 1X2 probabilities and uncertainty interval.
3. Use the lower probability bound for an entry decision.
4. Calculate a target exposure subject to variance, exposure, and daily-loss limits.
5. Buy/add only when target exposure rises and risk gates pass.
6. Reduce only when the current model no longer supports the open exposure.
7. Never reverse/short automatically in the first production version.
```

This avoids chasing noisy in-play moves. The initial `target_yes_position` function uses
uncertainty-adjusted edge and per-contract outcome variance, then caps the result under
`StrategyConfig`. It is deliberately not full Kelly and must be re-estimated from
historical in-play data before any production use.
