# Sprint Completion — Evaluation Reset + Multi-Competition Event Data Expansion (2026-06-22)

Branch `evaluation-reset-event-expansion`. All in-play models remain research_only / experimental /
not_runtime_approved. **B1 is still the sole runtime model; protected files unchanged vs
`approved-b1-runtime`; `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`.**

## 1. Prior claims that REMAIN VALID
- **In-play >> static B1**: the single largest, robust gain (RPS ~0.19 → ~0.15). Confirmed on historical
  LOGO and as a pre-specified (non-selected) comparison on 2026.
- **Historical leave-one-competition-out**: M2/M6 beat the time+score baseline M1 across the pre-2026
  tournaments; **market ≈ Elo** as an in-play anchor (M6 vs M2 ns).
- **Player-plane pre-match negative**: lineup/XI-strength/key-availability do not beat Elo.
- **Temperature scaling improves calibration** as a general statistical fact (not a 2026-specific claim).

## 2. Claims DOWNGRADED to exploratory (selection-on-test)
- "**M2fit_temp is the best in-play model**" and all "best on the 2026 World Cup" rankings
  (M2temp/M2fit/M2fit_temp). They were built/crowned after repeatedly viewing 2026 results. Real
  numbers, but **exploratory, not out-of-sample validation**. (Registry + `inplay_result_status_registry.yaml`.)

## 3. Does M2fit_temp survive NESTED historical evaluation?
**No.** Under nested leave-one-competition-out (302 men's international matches, no 2026, no test
peeking), the inner loop selects **plain M2 in 4/6 folds and M5 in 2/6 — M2temp/M2fit/M2fit_temp are
never selected**. Nested-selected outer RPS 0.1487 is *worse* than always using plain M2 (0.1474).
**Reference in-play model = M2.** Nested-vs-M1 dRPS −0.0042, CI [−0.0083, +0.0002] (ns).

## 4. Does xG add value after proper cross-competition evaluation?
**No.** All six pre-registered xG families (and all-xG) are ns vs M1 on a 6-competition LOGO; no xG
variant is ever selected in nested CV. The earlier underpowered 2-competition xG test is now confirmed
with proper power. (Next-goal — where xG is theoretically strongest — is data-blocked, see §6.)

## 5. Does club data transfer to international?
**Not testable with current ratings → effectively blocked.** The club auxiliary (La Liga 2015/16, 60
matches) was built, but **club teams have no Elo anchor** (`elo_history` is national-team only), so the
Elo-anchored in-play models cannot train/score on it. A club rating source (or a non-Elo anchor) is
required before club→international transfer can be tested. Domains were never silently mixed.

## 6. Is player / card / substitution modeling data-ready?
**No — all blocked by data thresholds** (`player_card_substitution_readiness.md`):
- player/substitution model: 374 matches with lineup+subs < 500 → **BLOCKED**.
- direct-red / second-yellow model: 50 positive events < 150 → **BLOCKED**.
- next-goal model: 374 matches < 500 → **BLOCKED**.
Root cause: StatsBomb open data contains only ~333 men's **senior international** matches in total — an
**unavailable-data** ceiling, not a processing gap. Club data could pad counts but transfer is unproven
and mixing is disallowed.

## 7. Untouched future 2026 matches for final prospective scoring
As of the freeze (2026-06-22T21:24:39Z): **41 finished (seen → exploratory), 1 live, and 30 not-started
(NS) — the prospective pool**. Knockout fixtures not yet scheduled will add more. These 30+ matches are
genuinely untouched by model selection and are the clean test for the frozen model
(`configs/final_holdout_model.yaml`).

## 8. Exact data sources still needed
- **More men's senior international event data** (to lift player/next-goal/red models over threshold) —
  not available in StatsBomb open data (capped ~333); would need a paid event provider (e.g., API-Football
  Pro covers events but limited xG; StatsBomb commercial; Opta) — a PAID/EXTERNAL action.
- **A club rating (Elo-equivalent)** to enable the club→international transfer test.
- Continued accrual of **2026 results** (time-gated) for prospective scoring.

## 9. Next highest-value task
**Score the frozen model prospectively on the 30 untouched 2026 matches as they finish** (paper, scoring
only) — the first genuinely clean OOS evaluation — and **adopt plain M2 as the reference in-play model**
(optionally re-freeze to M2 for a cleaner prospective baseline). No new modeling "improvement" should be
claimed until the prospective scores exist.

## Verification (Phase 7)
- `pytest -q`: **184 passed**.
- Protected scope (`git diff approved-b1-runtime..HEAD`): **unchanged**.
- Datasets gitignored (append-only raw under `data/raw/statsbomb`); reports + code + tests committed.
