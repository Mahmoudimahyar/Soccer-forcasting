# Tier 2 — Baseline Gate

Authoritative pre-autoresearch gate. Built on branch `tier-2-pre-match`.
Suite: `scripts/tier2_baselines.py` → `outputs/research/tier2/`. Tests: `pytest -q` → 61 passed.

## Protocol used
- **Selection: DEV folds only** (train<2010→2010, train<2014→2014, train<2018→2018).
- **Gate: 2022 read ONCE** (not used for tuning). **Locked: 2026-MD1** (transfer only).
- Calibration fit on **train data only** (latest pre-cutoff tournament as the B7 calibration split).
- B6 (no-vig market) **only on folds with real timestamped odds (2022)**; compared only on that
  same subset. B7 has **no-market** (all folds) and **market** (2022) variants. No fake odds.
- Every model emits 3-way probs; B4/B5 also expected goals; richer per-prediction fields
  (entropy, interval, completeness, model version, decision timestamp) are produced for the locked
  fold sample (`MODEL_VERSION="tier2-baselines-v1"`).

## Results — DEV (composite, lower better; mean over 2010/14/18)
| Model | dev mean | dev worst-fold | dRPS vs B1 (95% CI) | sig vs Elo? |
|---|---|---|---|---|
| **B1 Elo** | **0.3553** | 0.3796 | — | baseline |
| B4 Poisson | 0.3569 | 0.3838 | +0.0006 [-0.0050,+0.0061] | no (tie) |
| B5 Dixon-Coles | 0.3580 | 0.3781 | +0.0008 [-0.0048,+0.0066] | no (tie) |
| B7 no-market ensemble | 0.3590 | 0.3791 | +0.0011 [-0.0059,+0.0077] | no (tie) |
| B3 Elo+host | 0.3634 | 0.3759 | +0.0027 [-0.0101,+0.0158] | no (tie) |
| B2 FIFA-only | 0.3968 | 0.4580 | +0.0237 [+0.0035,+0.0426] | **worse** |
| B0 prior | 0.4187 | 0.4217 | +0.0570 [+0.0301,+0.0851] | **worse** |

Paired bootstrap on 144 pooled DEV matches (2000 resamples). **dRPS<0 would mean better than Elo.**

## Gate (2022, single read) and Locked (2026-MD1, transfer)
- **2022 gate composite:** B2 FIFA 0.387, B6 market 0.394, B7_market 0.403, B0 0.404, B1 0.416,
  B4 0.423, B5 0.426, B7_nomarket 0.432, B3 0.470. (Market & FIFA look best here — one fold only.)
- **2026-MD1 locked composite:** B5 0.398, B4 0.406, B3 0.415, B2 0.417, B7_nomarket 0.425,
  B1 0.427, B0 0.430. (Scoreline models transfer best on this 24-match sample.)
- **Calibration:** per-fold draw slope/intercept are too noisy to discriminate (≈10–13 draws per
  48-match fold; B7 slope ranged 0.5→19.5). Aggregate dev reliability is acceptable (B7 pooled:
  bin 0.1–0.2 pred 0.184/act 0.182; 0.2–0.3 0.242/0.267). draw-interval coverage = 1.0 on dev.

## Gate questions
1. **Is Tier 2 ready for autoresearch?** **Yes, technically** — the baseline suite is reproducible,
   leakage-safe, and rigorously evaluated with bootstrap uncertainty. **But** the evidence says the
   modeling ceiling on free data is ~Elo, so unconstrained architecture autoresearch is low-yield;
   autoresearch should be **bounded and market/feature-anchored**, not free-form.
2. **Which models are valid?** B0, B1, B2, B3, B4, B5, B7(no-market) on all folds; B6 and B7(market)
   on **2022 only**. All reproducible from tracked code + approved sources.
3. **Which are unavailable due to missing data?** B6 / market features for **2010/2014/2018** (Odds
   API history starts 2020-06); `low_block_risk` (market-derived) everywhere; in-play/player/xG.
4. **Must any previous result be discarded?** Yes — the original fixed-evaluator run on the buggy
   cross-tournament group-state table (superseded). The candidate blend weight (0.85) was selected
   with a sweep that touched 2022; **re-established here with dev-only selection + a single 2022 gate
   read**. Synthetic seed odds never entered any metric.
5. **Does B7 actually improve over B1?** **No.** B7(no-market) dRPS vs Elo = +0.0011 with 95% CI
   [-0.0059, +0.0077] — indistinguishable from Elo (and slightly worse in point estimate). Its only
   edge is occasional draw-calibration, not sharpness. **No baseline robustly beats Elo-only.**
6. **Next bottleneck: architecture or data?** **Data.** Across Tier-2 + prior cycles, no architecture
   beat Elo with significance; the only signals that beat Elo (market on 2022; the auxiliary intl
   beat-market result) require **odds history we don't have for the dev folds**. Modeling is at its
   ceiling; data is binding.
7. **Three highest-value data requests:**
   1. **Historical multi-book pre-kickoff odds for 2010–2018** (and broader pre-2020) — makes B6 and
      a market-anchored B7 *backtestable across all folds* (currently only 2022). `ODDS_API_KEY` paid
      tier does not reach pre-2020; needs an alternative archived-odds source. See
      `data_requests/pending/odds_api.yaml`.
   2. **Fresher / forward-looking strength for 2026** (FIFA release ≥2025, or an updated Elo input) —
      the current FIFA snapshot for 2026 is 635 days stale.
   3. **Time-safe historical international lineups + xG** (for an orthogonal, non-redundant signal) —
      currently unavailable for WC/Euro (see `tier_2_existing_work_audit.md`).

## Approved baseline
**B1 — Elo-only three-way model — is the currently valid approved baseline.** Any Tier-2 candidate
must beat B1 with a paired-bootstrap CI that excludes 0 on the DEV folds (not merely a better point
estimate), and must not regress the 2022 gate, to be promoted.

## Status
Tier-2 baseline gate complete. **STOPPING — no autoresearch / no experimental `candidate.py` edits
until you explicitly approve this gate.** (Branch `tier-2-pre-match` holds the new scripts + reports,
currently uncommitted, ready to commit on your instruction.)
