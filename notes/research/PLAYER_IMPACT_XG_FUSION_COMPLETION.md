# Player-Impact, Substitution-Delta & xG Fusion Research V1 — Completion

research_only=true · experimental=true · not_runtime_approved=true · not_trade_eligible=true ·
not_live_eligible=true · KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Worktree `C:/Users/Mahyar/worldcup-player-impact-xg`, branch `player-impact-xg-fusion-v1`
(base tag deep-research-inplay-foundation-v1 @ 6136443).

## Honest outcome
The run SUCCEEDS by producing preregistered honest outcomes **#2 (player-impact/substitution-delta rejected)**
and **#5 (xG fusion not concludable — limited sample + pipeline join not wired)**. **No model qualifies for a
shadow-candidate review. No promotion.**

## Controller runtime & job statuses
Reused restart-safe controller; run_id `pi_main`. Initial pass 166 s + idempotent resume (after a JOB6 path-bug
fix). Final: **11 complete, 2 skipped, queue_complete** (<<6h). The restart-safe + fail-closed design again
validated (a wrong StatsBomb path → JOB6 skipped → one-line fix → resume re-ran only JOB6/JOB10/JOB13; no API re-pull).
- JOB1-5 complete; JOB6 complete (StatsBomb bridge + xG build recognized); JOB7 (P) complete; JOB8 (N) complete;
  JOB9 (discipline) **skipped** (sendings-off 123 < 150 in this worktree's corpus view); JOB10 (xG fusion)
  **skipped** (honest outcome #5); JOB11 ablation, JOB12 calibration, JOB13 summary complete.

## API request usage
**100 API-Football requests** (bounded inline backfill = 60 club fixtures). The predeclared 1,713-fixture
backfill (budget research_budget 3,477) is committed + **resumable** (`scripts/player_history_resume.py`); it was
intentionally bounded for this session. **No Odds API call.** No key revealed.

## Corpus growth & player-history coverage
This worktree view: 900 reconciled fixtures + 60 new club = 960; 100% regulation reconciliation. Player-history:
**19,943 appearances, 0 leakage violations** (causal audit), 19,800 player-prior rows / 1,800 lineup-aggregate /
7,178 substitution-delta rows. Cold-start ~22-27% surfaced via history_completeness / unknown_player flags.

## Exact club/national-player linkage rate
**1.000** exact API-Football player-id linkage (JOB5); NO fuzzy name linking; unmatched/ambiguous handled explicitly.

## StatsBomb bridge & xG feature coverage
**258 exact-matched senior men's international games** (WC2018 64, WC2022 64, Euro2024 51, Euro2020 51,
Copa2024 28), bridge digest c43a30b5…; rejects = qualifiers/timezone (strict, no fuzzy). 60 game-event files
cached; xG event-state features build rc=0 for the cached subset. **xG features were NOT joined into the
international in-play snapshots in this run** -> X0-X3 fusion not evaluable (the documented remaining gap).

## P1-P4 (W/D/L, LOCO international, RPS lower=better)
| model | RPS | logloss | match-bootstrap 95% CI |
|---|---|---|---|
| P1 pre-match XI impact | 0.1515 | 0.811 | [0.152, 0.174] |
| **P2 +on-pitch impact (leader)** | **0.1500** | 0.788 | [0.149, 0.170] |
| P3 +substitution-delta | 0.1500 | 0.795 | [0.150, 0.181] |
| P4 +team-state | 0.1500 | 0.795 | [0.150, 0.181] |
**P2 ties W2 (0.150) — it does NOT beat the reference.** Bootstrap CIs overlap heavily; improvement is not
consistent across folds; the preregistered success rule is NOT met -> **REJECTED**.

## Ablation (decisive)
full_model_rps 0.150. Removing **score-state** worsens RPS by **+0.0738** (dominant). Removing the
**player-impact channel (player_count_diff): delta_rps = 0.000** — player-impact contributes nothing. Discipline
+0.0003, substitutions -0.0004, time +0.0002 (noise). most_valuable_group = **score_state**. Quantitative proof
that in-play SCORE dominates and player-impact / substitution / discipline features add ~0 over W2.

## N0-N3 (next regulation goal in 15 min; Brier)
N0 0.2393, **N1 0.2373 (leader)**, N2 0.2373, N3 0.2378. Player-impact (N2) + substitution-delta (N3) add
NOTHING over N1; N1 barely beats base-rate.

## C0-C1 (discipline)
C0 base-rate computed; **C1 SKIPPED** — sendings-off 123 < 150 preregistered positive-event threshold in this
worktree's corpus view (the larger backfill / deep-research extension would lift this; insufficient here).

## X0-X3 (xG fusion)
**Not evaluated (honest outcome #5).** The exact bridge (258 games) + xG event-state features exist + are
tested, but the xG-state↔international-snapshot join was not wired in this run, and the matched-with-events
sample (~58-60 games) is small/low-powered. No fusion conclusion is drawn — by design, not forced.

## Calibration & uncertainty
P2/W3 draw calibration reasonable; 45 overconfident failures flagged. Bootstrap at MATCH level only (correlated
snapshots not treated as independent). Reliability improves by minute (information accrues).

## Research-only leader / rejections
**Leader: none qualifies.** P2 only ties W2; P1/P3/P4 worse-or-equal; N2/N3 no gain; C1 insufficient data;
X1-X3 not evaluable. All candidate families are REJECTED or NOT-CONCLUDABLE under the frozen preregistration.

## Future shadow-candidate review?
**Not justified by this run.** No feature family beat W2 robustly. The strongest signal remains the in-play
score-state (already captured by W2/score features). Revisit only with (a) the full 1,713-fixture player-history
backfill for denser priors AND (b) a wired xG-state↔snapshot join on a LARGER matched international xG sample.

## What remains blocked
- Per-shot xG at scale: API-Football lacks it; StatsBomb-open international overlap is small (258 games, ~60 with
  events) -> low-powered xG fusion. A larger/licensed xG source would be needed for a powered test.
- C1 discipline: needs >=150 sendings-off (resume the backfill / include the deep-research extension raw).

## Why B1, M1-M5, frozen M2, trading, and Kalshi remain unchanged
NO model was trained for promotion and none was modified. B1 remains sole runtime; active M1-M5 + frozen
prospective M2 + candidate.py + approved_models.yaml untouched; trading/risk/Kalshi/paper untouched;
KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper. The collector was never written to; the research task was
registered (Task Scheduler confirmed) then removed; all outputs are historical research-only, not live/trade eligible.
