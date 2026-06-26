# Commentary Precision & Historical Weak-Supervision Quality Gate V2 — Completion

research_only=true · historical_weak_supervision_only=true · not_runtime_approved=true ·
not_trade_eligible=true · not_live_eligible=true · KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Worktree `C:/Users/Mahyar/worldcup-commentary-intelligence`, branch `commentary-precision-weak-supervision-v2`.

## Collector isolation result (verified)
Active collector untouched: main checkout `worldcup_draw_model_lab_FINAL`, `v1-5-prospective-operations` @
**dc73318**, tracked-clean, task Ready, heartbeat advancing (…04:43Z). `git diff dc73318..HEAD` =
**116 Added, 0 Modified** (no pre-existing collector file changed). 52 tests pass. No odds/API-Football
calls; no .env access; no raw commentary/label text or secret tracked; all raw + my processed outputs
gitignored; runtime/trading import-isolation clean (no precision/silver/commentary import).

## Data volume
254 overlapped games (whisper_v1_en), 6 competitions, 17 seasons, **383,591** commentary segments,
**20,450** supported events / 12 classes. Duplicate segment rate 0.21 (deduped by content_hash).

## Evaluation protocol
Leave-one-competition-out (6 folds). Fitting + threshold selection + vocabulary on TRAIN competitions only;
no random row splits; no test-competition tuning. Precision = emitted segment has a real event of that class
within 45 s (half-relative). Ladder: R0 time-only, R1 rules+negation, R2 TF-IDF+logreg, R3 hybrid,
R4 abstention (train-selected threshold, target train precision 0.85).

## Exact preregistered thresholds (FROZEN before fitting; NOT changed after results)
≥50 emitted labels; Wilson 95% LB on precision ≥0.80; median |dt| ≤15 s; p90 |dt| ≤35 s; Wilson LB ≥0.80 in
≥4 folds (≥5 preds each); not from a single competition.

## Event-class results (R4 aggregate) & gate decision
| class | n | precision | Wilson LB | median t | stable folds | decision |
|---|---|---|---|---|---|---|
| corner | 2129 | 0.786 | 0.768 | 14.5 | 1 | usable_only_with_low_confidence_flag |
| foul | 1737 | 0.788 | 0.768 | 7.0 | 0 | usable_only_with_low_confidence_flag |
| yellow_card | 217 | 0.788 | 0.729 | 5.2 | 0 | usable_only_with_low_confidence_flag |
| goal | 76 | 0.671 | 0.559 | 2.0 | 0 | insufficient_precision |
| shot / shot_on_target | 108/81 | 0.60/0.57 | 0.51/0.46 | 2–4 | 0 | insufficient_precision |
| penalty_awarded | 114 | 0.132 | 0.081 | 25.0 | 0 | insufficient_precision |
| offside / substitution / kickoff | 42/43/24 | — | 0.39–0.53 | — | 0 | insufficient_coverage |
| red_card / second_yellow | 30/19 | 0.27/0.21 | 0.14/0.09 | — | 0 | insufficient_coverage |

## Approved silver-label classes: **NONE (0)**.
The high-precision silver dataset is EMPTY. This is an honest negative result under a preregistered bar.

## Rejected classes
- usable_only_with_low_confidence_flag (retain as flagged historical signals, NOT silver): corner, foul, yellow_card.
- insufficient_precision: goal, shot, shot_on_target, penalty_awarded.
- insufficient_coverage: offside, substitution, kickoff, red_card, second_yellow.

## Timing quality
Among emitted labels, median |dt| 2–15 s and p90 ≤33 s for the near-miss classes (timing was NOT the binding
constraint — precision/stability were). goal narration is near-instant (median ~2 s) when present.

## Coverage vs precision tradeoff
R4 abstention buys precision at large coverage cost (goal 0.15→0.67 precision but n 9860→76; yellow 0.63→0.79
but n 981→217). Even at maximal abstention the best classes plateau at ~0.79 aggregate precision (Wilson LB
~0.77) — short of 0.80 — and corner is unstable (Serie-A fold 0.67 vs 0.81–0.87 elsewhere).

## Downstream coverage-recovery verdict
**insufficient_quality_or_coverage** — with 0 approved classes there is nothing to reconstruct masked
structured labels with at the required confidence. No outcome model trained (by design). No predictive or
market-edge claim is made.

## Multilingual limitation
English pipeline only: goal recall 0.88 (English translation) vs 0.05 (original-language ASR) on the same
held-out league. Building broad multilingual models is not justified by source value/rights.

## Allowed use
Rights classifications; "labels openly obtainable (no NDA)"; the reproducible per-class precision/recall/
timing; corner/foul/yellow_card as ~0.73–0.77 Wilson-LB LOW-CONFIDENCE historical signals; tooling exists + tested.

## Prohibited use
Any live, delayed-live, point-in-time, predictive, market-edge, or trading/paper-trading use; any
high-precision silver-ground-truth claim; any player-level claim; any original-language generalization claim;
entry into runtime / B1 / frozen M2 / M1–M5 / Kalshi / risk / the active collector.

## Exact next recommended action
Stop investing in SoccerNet commentary as a high-precision silver source. Retain corner/foul/yellow_card as
flagged low-confidence historical signals only. For player/next-goal/card models, procure a paid STRUCTURED
event provider (Sportmonks lowest-cost; StatsBomb/Opta richer). For any LIVE use, procure a paid commentary
feed with verified publication timestamps + pass the causal gate.

## Should the project keep investing in SoccerNet? / higher-value route
Diminishing returns for SoccerNet commentary. Ranked routes: (1) paid structured event provider
(player/next-goal/card), (2) paid live commentary feed (only path to live), (3) SoccerReplay-1988 NDA
(historical richness only; no live, no precision-bar guarantee), (4) further SoccerNet tuning (low value).

## Operations integrity note
Mid-sprint, the worktree branch ref `commentary-precision-weak-supervision-v2` was zeroed by a filesystem
fault (41 null bytes). No commits were lost: `git fsck` was clean, the ref was restored to the last good
commit (b305453) from the worktree reflog, and the Phase-5 work was recommitted. The active collector's ref
(`v1-5-prospective-operations`) was never involved.
