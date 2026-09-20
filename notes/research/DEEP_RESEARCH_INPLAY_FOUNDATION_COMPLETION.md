# Deep Research Controller and In-Play Foundation V1 — Completion

research_only=true · experimental=true · not_runtime_approved=true · not_trade_eligible=true ·
not_live_eligible=true · KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Worktree `C:/Users/Mahyar/worldcup-deep-research`, branch `deep-research-inplay-foundation-v1`
(base tag api-football-historical-corpus-v1 @ 6ddf60a).

## Controller runtime & job statuses
Bounded restart-safe controller; run_id `night_main`. Elapsed **277.8 s** initial pass; queue completed
(<<4h cap). The 4 evaluation jobs failed on a relative-import bug; the controller (correctly) CONTINUED past
the non-critical failures and wrote a full summary, then a one-line fix + **idempotent resume** re-ran only
the failed jobs (JOB2 stayed complete → NO re-pull). Final: **all 11 jobs complete**, stop_reason
`queue_complete`. This is the restart-safe + fail-closed design validated end-to-end.

## API request usage
**440 API-Football requests** (JOB2 extension: 220 fixtures × events+lineups). Controller cap 600; reserve
respected; **no Odds API call**; no key revealed.

## Active-collector isolation result
Collector untouched: main `worldcup_draw_model_lab_FINAL`, `v1-5-prospective-operations` @ **dc73318**,
tracked-clean, task Ready, heartbeat advancing (…07:08Z). `git diff dc73318..HEAD` = **65 Added, 1 Modified**
(the 1 = `tests/conftest.py`, the Phase-1 integration-test-skip extension — a test-infra file, NOT collector/
model/trading). Scheduled task `WorldCupDeepResearchNightRun` was registered (Task Scheduler confirmed
state=Ready) then REMOVED after completion. `pytest -q` = 212 passed / 20 skipped (clean).

## Corpus size & sending-off count (before → after)
- Fixtures: 900 → **1,120** (+220 predeclared club extension, metadata-only selection).
- Sendings-off: 123 → **176** (≥150 → discipline C1 threshold MET via unbiased extension).
- Reconciliation: **1,120 / 1,120 regulation-exact (100%), 0 unresolved exceptions.**

## Readiness
- Player/substitution: READY (627 international + 493 club lineup/sub matches; ≥500).
- Next-goal (regulation): READY (627 intl clean timestamped matches; ≥500).
- In-play W/D/L (regulation): READY (627 intl, 100% reconciled).
- Discipline C1 (sending-off): READY (176 ≥ 150).

## W0–W4 results (LOCO international, RPS lower=better; n=627 matches)
| model | RPS | logloss | brier_draw | RPS match-bootstrap 95% CI |
|---|---|---|---|---|
| W0 static base-rate | 0.2331 | 1.079 | 0.187 | [0.233, 0.250] |
| W1 score-diff empirical | 0.1515 | 0.811 | 0.171 | [0.152, 0.174] |
| **W2 remaining-time Poisson** | **0.1500** | **0.788** | 0.165 | [0.149, 0.170] |
| W3 +team-state logistic | 0.1500 | 0.795 | 0.169 | [0.150, 0.181] |
| W4 +lineup-continuity | 0.1500 | 0.795 | 0.169 | [0.150, 0.181] |
**Leader: W2.** W3/W4 do NOT improve over W2 (RPS ties, logloss slightly worse, CIs overlap heavily).

## N0–N2 results (next regulation goal in 15 min; Brier lower=better)
| model | Brier | logloss | cal slope | ECE |
|---|---|---|---|---|
| N0 base-rate (0.389) | 0.2393 | 0.672 | −1.25 | 0.017 |
| **N1 logistic hazard** | **0.2373** | 0.668 | 0.54 | 0.041 |
| N2 +continuity | 0.2373 | 0.668 | 0.54 | 0.041 |
**Leader: N1**, but it barely beats base-rate; N2 lineup-continuity adds nothing.

## C0/C1 results
C0 yellow-state rate 0.497. **C1 ran** (176 sendings-off ≥ 150) — no skip; positive-event count sufficient.

## Club-to-international transfer result
**transfer_neutral** — held-out international W3 RPS 0.1559 (intl-only) = 0.1559 (club-auxiliary). Club data
does NOT improve international W/D/L. (Club auxiliary-only; evaluated only on held-out international; no pooling.)

## Calibration & failure-analysis summary
W3 draw calibration slope 1.20, intercept 0.10, ECE 0.033 (reasonable). 45 overconfident failures (conf>0.7,
RPS>0.5). Reliability by minute improves as expected (RPS 0.213@15' → 0.094@75'). Bootstrap at MATCH level
only (correlated state rows not treated as independent).

## Research-only leaders / failed families / what cannot be concluded
- LEADERS (research-only): **W2** (in-play W/D/L), N1 (next-goal, marginal).
- FAILED to generalize: **W3, W4** (team-state + lineup features add nothing over W2); **N2** (continuity);
  **club→international transfer** (neutral).
- CANNOT conclude: that richer team-state/lineup features help in-play W/D/L or next-goal at this corpus size;
  no per-player causal claim; no xG/shot-quality (provider gap). Differences within the bootstrap CIs are not
  significant.

## Shadow-candidate review?
**No new model qualifies.** W2 is the strong simple baseline and is essentially the existing frozen
remaining-time Poisson (M2) reimplemented — it is NOT a new candidate. The feature-rich families did not beat
it. Recommendation: do NOT advance any model to shadow-candidate review from this run; revisit only with more
international matches and/or a richer feature source (e.g., xG via a different provider).

## Why B1, frozen M2, active M1–M5, trading, and Kalshi remain unchanged
This sprint trained NO model for promotion and modified none. B1 remains the sole approved runtime model;
frozen prospective M2 + active M1–M5 + candidate.py + approved_models.yaml untouched; trading/risk/Kalshi/
paper code untouched; KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper. All outputs are historical,
research-only, not live/trade eligible. The controller never wrote to the collector and stopped cleanly at
queue completion well within the 4-hour bound.
