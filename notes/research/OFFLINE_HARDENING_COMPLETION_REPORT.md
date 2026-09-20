# Offline Hardening Sprint — Completion Report (2026-06-23)

Parallel, offline-only sprint executed in an isolated worktree while the live `WorldCupShadowCollector`
kept running. All new work is research_only / not_runtime_approved / not_trade_eligible.
KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper.

## 1. Active-collector isolation result — CLEAN
- Worktree `C:\Users\Mahyar\worldcup-offline-hardening` on branch `shadow-offline-hardening-v1`
  (based on `dc73318`). All sprint work committed only here.
- The live collector's checkout (`...\worldcup_draw_model_lab_FINAL`) remained on
  `v1-5-prospective-operations` @ `dc73318` with **tracked files CLEAN** throughout.
- Scheduled task `WorldCupShadowCollector` unchanged (action/-File/workdir all point to the main
  checkout, not the worktree). Cadence, odds budget, M1–M5 logic, and frozen predictions untouched.
- No `.env`/`.env.example`/candidate.py/runtime/trading/risk/Kalshi file touched; no provider credential
  accessed or committed; raw data + large outputs remain gitignored.

## 2. Commits created (this branch)
- `c7d4dcc` Phase 0 setup — isolation manifest + worktree
- `e66bb19` Phase 0 — model-identity namespace + alias registry + validator (7 tests)
- `710823e` Phase 1/7B — 2022 replay semantics + full-tournament quality (9 tests)
- `f515000` Phase 2/7C — tournament simulator validation (7 tests)
- `8235435` Phase 3/7D — context-feature contract + leakage helpers (8 tests)
- `f355ccd` Phase 4 — prospective market scorecard + Tier gate (4 tests)
- (this report) Phase 5 — final audit + tag `shadow-offline-hardening-v1`

## 3. Model-ID namespace status — COMPLETE
Canonical registry (`schemas/model_identity_v1.yaml`, 12 models) + append-only alias map
(`configs/model_alias_registry.yaml`, 22 entries) + resolver/`annotate` (`model_identity.py`) +
validator. **prematch `M2` (market no-vig) is disambiguated from inplay `M2` (remaining-time Poisson).**
Invariants enforced + tested: exactly `prematch.b1_elo` is runtime-eligible; nothing trade-eligible; no
research model runtime-eligible; immutable rows never rewritten (annotate adds columns to a copy).

## 4. Replay coverage result — gate met
All **48 cached 2022 group matches reconcile exactly** (own-goal beneficiary, VAR-cancel, shootout kept
separate). **16 knockout matches classified `not_cached`** (offline cache gap; recoverable by a
read-only fetch, out of scope here). 0 score-reconciliation failures; 18 informational non-chronological
flags. 9 deterministic regression tests. Release rule satisfied (every available match reconciles;
every unavailable explicitly classified).

## 5. Simulator validation result — PASS
Official 2026 standings/tiebreak engine validated deterministically: points/GD/GF ordering, recursive
head-to-head, overall fallback, conduct + FIFA-rank tiebreaks, best-third ranking, top-2/4th advancement,
fully-played determinism, idempotent finalize, no-update-before-FINISHED. 7 tests + validator (all PASS).
Known limitations documented: explicit R32 bracket routing + knockout-round/shootout FORWARD simulation
are not implemented (the simulator outputs advancement probabilities) — out of scope, not claimed.

## 6. Weather/travel readiness result — causal-safe, research-only
Context-feature contract (`schemas/context_features_v1.yaml`, 14 features) + leakage-safe helpers
(haversine, rest-days, timezone displacement, neutral-site travel, weather forecast-vs-observed
eligibility) + availability policy + 8 tests. **No feature added to any model; no live weather call; no
fitting/ranking.** Forecast usable only if issued ≤ decision time; observed weather is retrospective-only.

## 7. Prospective scorecard readiness — ready, Tier A (gated)
Deterministic scorecard scores the frozen prematch models (canonical IDs) on one primary snapshot per
finalized match (T-15 > T-90 > baseline), with RPS/log-loss/draw-Brier/ECE/match-level bootstrap and a
Tier A/B/C gate. 4 sanitized-fixture tests. **Current clean prospective pool = 0 finalized eligible →
Tier A (informational only).** No model selection / recalibration / blend change / trading / edge claim.

## 8. Remaining true blockers
- **Future 2026 results** (time-gated): the 28 queued group matches must finish before any prospective
  comparison; the scorecard reaches Tier C only at ≥20 finalized eligible matches.
- **2022 knockout event cache** (data availability): a read-only API-Football fetch is needed to extend
  replay to the 16 knockouts (semantics + shootout handling already implemented/tested).
- **Venue-coordinate/timezone reference + approved weather source** (data availability): needed before
  per-fixture travel/weather features can be computed/used.
- **Paid event provider** (external/paid): still the only path to the player/next-goal/card thresholds.

## 9. What happens automatically as matches finish
The live collector keeps capturing T-90/T-15 odds + freezing M1–M5 + scoring finished matches (paper,
research-only). Re-running `prospective_market_scorecard.py` moves the finalized-eligible count toward
Tier B/C — yielding the first genuine out-of-sample B1-vs-market-vs-blend read (exploratory only).

## 10. What must NOT change until the prospective review gate is reached
Frozen prematch M1–M5 definitions/weights; the frozen in-play model; B1 runtime routing; trading flags
(KALSHI false / paper); the immutable ledgers (never rewritten — only annotated for canonical IDs). No
model selection, recalibration, blend-weight change, promotion, or trading at any tier below the stated
thresholds — and never a live-trading or Kalshi action.

## Verification
- New offline-hardening tests: **35 passed**. Full worktree suite: 222 passed, 13 skipped, 3 failed —
  the 3 are `test_inplay_dataset` requiring the **gitignored data absent in the worktree** (they pass in
  the data-bearing main checkout); they are unrelated to this sprint's additions.
- `git diff dc73318..HEAD`: additions only, plus one append to the research module `context_features.py`
  (not imported by the collector). Active checkout tracked-clean at `dc73318`.
