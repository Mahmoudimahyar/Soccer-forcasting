# Prospective Market Benchmark V1

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

The no-vig market (`M2_market`) is a **read-only comparator** — never a model feature, never a calibration target, never a trading signal.

- Fixtures: 34 (tier C_exploratory).
- RPS: B1=0.1304, market=0.1360 (B1 lower/better).
- Log-loss: B1=0.7754, market=0.7740.
- Draw-Brier: B1=0.1833, market=0.1765.

### Strata (descriptive)
- window: {'baseline': 31, 'final_pre_kickoff': 2, 'T-90': 1}
- matchday: {2: 11, 3: 23}
- a_fav/b_fav/near_even: 16/18/6

### Honest conclusion
On 34 fixtures the model–market gaps are small and bootstrap CIs overlap zero on every paired metric. There is **no evidence** that B1 or any blend beats the market (or vice-versa) at decision-grade confidence. A valid result may favor any of them; none is manufactured a winner. **Nothing is promoted to runtime; no trading rule is implied.**
