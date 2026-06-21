# Autoresearch Cycle 2 — Scoreline + In-Play capability (2026-06-21, branch `autoresearch-overnight`)

Track A of the two-track directive: build the research-only **scoreline** and **in-play** capability.
No new accounts/paid data used. **B1/Elo remains the only approved runtime model** — nothing here
clears the frozen promotion protocol, so nothing is promoted. `pytest -q` full suite green.

## 1. Pre-match scoreline layer — `src/wcdrawlab/research/scoreline.py`
Transparent goal-intensity model calibrated by Poisson MLE on TRAIN goals only:
`log λ_a = μ + β·(elo_delta/100)`, `log λ_b = μ − β·(elo_delta/100)`; Dixon-Coles adds low-score ρ.
Outputs per match: expected goals, full score matrix, **P(0-0), P(1-1), P(2-2)**, **P(U1.5), P(U2.5)**,
**P(BTTS No)**, 1X2, and a draw uncertainty interval.

### Strict ablation — scoreline 1X2 vs V8/B1 (DEV folds 2010/2014/2018)
| model | dev_2010 J | dev_2014 J | dev_2018 J | **dev mean J** |
|---|---|---|---|---|
| **V8 candidate** (incumbent) | 0.3770 | 0.3312 | 0.3541 | **0.3541** |
| B1 Elo (approved) | — | — | — | 0.3553 |
| scoreline Poisson | 0.3861 | 0.3322 | 0.3562 | 0.3582 |
| scoreline Dixon-Coles (ρ≈−0.05..−0.09) | 0.3817 | 0.3352 | 0.3527 | **0.3566** |

**Verdict:** the scoreline 1X2 does **not** beat V8/B1 (matches the known B4/B5 result). Dixon-Coles
beats independent Poisson (the negative ρ mildly inflates draws → better draw calibration). **Not
promoted.** Its value is the *additional* outputs, not 1X2 sharpness.

### Capability demo (DC, elo_delta=+120, fitted on <2018)
xG A=1.51 / B=0.92 · 1X2 = 0.506/0.272/0.222 · P(0-0)=0.094 P(1-1)=0.128 P(2-2)=0.042 ·
P(U1.5)=0.295 P(U2.5)=0.561 P(BTTS No)=0.525 · draw 95% CI [0.215, 0.328]. (These objective-#2
deliverables did not exist before this cycle.)

Tests: `tests/test_scoreline.py` (symmetry at Δ=0, valid probabilities, P(0-0)=e^-(λa+λb) for the
independent model, rows sum to 1, MLE recovers β≈0.5 from synthetic goals, DC fits + valid). All pass.

## 2. In-play replay layer — `src/wcdrawlab/research/inplay_replay.py`
Thin wrapper over the existing `wcdrawlab.inplay.engine` (remaining-time Poisson with red-card and
score-state dynamics, draw SE/CI, entropy). Adds the requested deliverables: **remaining expected
goals** (λ_a_rem + λ_b_rem), **risk band** (from normalized entropy), and a **replay harness**
(`replay_match`) that scores a sequence of decision-time snapshots using only information known at
each minute (no post-match data). Pre-match λ come from the scoreline mapping.

### Behavior validation (deterministic) — `tests/test_inplay_replay.py`
- minute 90, 1-0 → p(A win) > 0.95, p(draw) < 0.05, remaining xG ≈ 0. ✅
- kickoff, equal strength → symmetric 1X2, remaining xG ≈ λ_a+λ_b, draw within CI. ✅
- **red card to A** → p(A win) falls, p(B win) rises. ✅
- minute 85, 1-0 → p(A win) > 0.8. ✅
- remaining xG decreases monotonically through the match. ✅
- replay sequence: leading favorite's win prob rises, entropy falls by full time; every row carries
  remaining_xg_total + risk_band. ✅

**Real event-time scoring** (in-play RPS/log-loss, draw calibration by minute bucket, red-card
response curves) requires timestamped historical event feeds, which are **not yet available**
(BLOCKERS B-1: API-Football auth now works but free-tier 2026 coverage unconfirmed; no historical
event store). The transparent benchmark + harness are in place to score the moment data lands.

## Governance
- `candidate.py` unchanged (V8); scoreline + in-play are **research-only modules**, not runtime models.
- B1 remains the sole approved model; no promotion (no candidate cleared ≥0.002 dev gain).
- No `.env`/trading/risk/Kalshi/provider-credential changes; paper mode intact.

## Next
- Score the in-play model by historical replay once an event feed is available (verify free-tier
  API-Football 2026 coverage with one call; else StatsBomb open historical for offline replay).
- On approval, the odds pilot (`data_requests/pending/odds_api_2022_group_stage_pilot.yaml`) enables
  the market-vs-B1 test — the only evidenced path to beat Elo on 1X2.
