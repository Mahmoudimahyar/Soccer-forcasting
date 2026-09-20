> [!NOTE]
> **CAVEAT ADDED (banner added 2026-09-20; original text and numbers kept unedited below).**
>
> The market comparator here is an **early line, not a closing line**. The strata line below
> (`baseline: 31, final_pre_kickoff: 2, T-90: 1`) means that for 31 of 34 fixtures the market is a 2026-06-21
> baseline snapshot, a median of about 98 hours before kickoff.
>
> The cause was a payload-key mismatch that made the prediction freezer ignore all 47 later collector snapshots
> (fixed 2026-09-20; the immutable ledger and the numbers below are unchanged).
>
> The conclusion is unchanged — no evidence either way at this sample size, Tier C (the lab's own "exploratory"
> label for 20-49 fixtures), nothing promoted — but it must not be read as a comparison against closing odds.
>
> See [ERRATA E2](../../docs/ERRATA.md), [PROSPECTIVE_SHADOW_SCORECARD_V1.md](PROSPECTIVE_SHADOW_SCORECARD_V1.md) and the
> [glossary](../../docs/GLOSSARY.md).

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
