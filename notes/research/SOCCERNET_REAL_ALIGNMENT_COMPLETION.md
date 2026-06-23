# SoccerNet Real Commentary-to-Event Alignment & Weak-Supervision Validation V1 — Completion

research_only=true · historical_weak_supervision_only=true · not_runtime_approved=true ·
not_trade_eligible=true · not_live_eligible=true · KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Worktree `C:/Users/Mahyar/worldcup-commentary-intelligence`, branch `commentary-alignment-real-data-v1`.

## Active-collector isolation result (verified)
- Active collector untouched: main checkout `C:/Users/Mahyar/worldcup_draw_model_lab_FINAL`,
  branch `v1-5-prospective-operations` @ **dc73318**, tracked-clean; WorldCupShadowCollector task State=Ready,
  workdir = MAIN checkout (not a worktree); heartbeat advancing through the sprint (…16:23 → 16:48 → 16:53Z),
  budget 6/500 credits, dry_run=false.
- `git diff dc73318..HEAD` = **83 files Added, 0 Modified** — no pre-existing collector file changed.
  Sprint commits exist only on the worktree branch; collector `src/` is byte-identical to baseline.
- Adversarial 5-lens audit (isolation / rights+secrets / leakage / honesty / reproducibility+runtime
  isolation): **5/5 PASS**. All raised flags were minor and have been addressed (see below).

## Official action-label source + license status
- Source: official **SoccerNet** pip package (`SoccerNetDownloader.downloadGames(files=["Labels-v2.json"])`).
- **No NDA/password used or required for LABELS** — the NDA password gates VIDEOS only. Empirically
  confirmed: labels downloaded with no password. Classification: **verified_open_research_download**.
- License: SoccerNet labels = non-commercial research + attribution. SoccerNet-Echoes commentary = CC BY 4.0.

## Acquired files & checksums (raw, gitignored)
- SoccerNet-Echoes: `whisper_v1` Arrow (sha256 3fc34c47c4bc…) + `whisper_v1_en` Arrow. Manifest:
  `commentary_soccernet_sample_manifest.json`.
- SoccerNet labels: 385 `Labels-v2.json` (train+valid+test), 22,551+ events, 17 classes. Manifest:
  `soccernet_action_label_manifest.json`. All raw stored only under gitignored `data/raw/…` (0 tracked).

## Overlap & mapping quality
- Exact SoccerNet game-path join (after stripping Echoes half-suffix): **373** matched games (whisper_v1) /
  **254** (whisper_v1_en, primary). 0 normalized/ambiguous/override; **0 collisions**; no fuzzy matching.

## Event-taxonomy coverage
- 17 SoccerNet classes → canonical taxonomy; 12 keyword-evaluable. **Unsupported by this source**:
  own_goal, penalty_scored/missed, VAR_review, VAR_goal_cancelled, halftime, fulltime; **no player IDs**
  (entity alignment limited to team side).

## Alignment metrics (whisper_v1_en, leave-one-competition-out; reproduce: `python scripts/run_soccernet_folds.py`)
- goal recall **0.62–0.88** across all 6 folds (precision 0.16 — keyword polysemy); **corner recall
  0.40–0.75 at precision 0.64–0.82** (best class); yellow_card / foul precision **0.70–0.75**; offside
  recall 0.65; shots recall ~0.55–0.60 precision ~0.32–0.39; substitution recall 0.09 / kickoff 0.006
  (poorly narrated by the pre-registered phrases); rare events (red_card n=6, second_yellow n=5) unreliable.
- Stable across folds → generalizes. Full per-type/per-competition tables in `soccernet_real_alignment_evaluation.md`.

## Timing findings
- |dt| median/mean ≈ **4–18 s** for common events (up to ~32 s for rare classes). Train-only latency
  offset ≈ 0.4–0.9 s (small); calibrated vs uncalibrated nearly identical.

## Language-dependence finding (reproducible)
- English keyword rules on original-language ASR collapse goal recall to **0.0535** vs **0.8846** on the
  English-translation variant (`soccernet_language_and_fold_comparison.json`). A production system needs
  per-language rules or translated commentary.

## Readiness decision
**ready_for_historical_weak_supervision_only** (option 2 of 5). Usable as noisy distant labels for salient
events; NOT clean ground-truth enrichment (precision too variable for several classes); overlap (254) far
exceeds the 20-match feasibility floor; labels are NOT source-blocked.

## Explicit live-use prohibition
SoccerNet-Echoes has **no verified publication_time** → can NEVER be a live feature, never enter the active
collector, never influence prospective predictions, never be treated as point-in-time, never trading/paper.
The fail-closed live-eligibility gate + runtime/trading import-isolation tests enforce this in code.

## Audit flags addressed
- Per-competition 6-fold table is now reproducible via committed `scripts/run_soccernet_folds.py`.
- Original-language 0.05 result persisted reproducibly in `soccernet_language_and_fold_comparison.json`.
- Report prose corrected: timing tail (~32 s rare classes), goal-recall low end stated as 0.62 (Bundesliga 0.625).

## Remaining blockers & next best action
- None internal: all feasible phases complete + tested. Limitations are source-intrinsic (no player IDs /
  own-goal / VAR in SoccerNet v2; original-language keyword gap).
- **Exact next best action**: extend keyword rules to be per-language (or always use whisper_v1_en) and add
  goal/shot disambiguation patterns to lift precision — all still historical-only.
- **Paid live-commentary provider**: still required for ANY live/delayed-live use (SoccerNet route is
  historical-only by construction). Unchanged from prior sprint.
- **SoccerReplay-1988 / NDA source**: would add denser aligned commentary + (potentially) player-level
  detail SoccerNet v2 lacks — unique value for entity-aware (Level-2) alignment and substitution recall;
  remains an external NDA decision. Not required for the historical weak-supervision result delivered here.

## Allowed vs prohibited claims
- ALLOWED: rights classifications; "labels are openly obtainable (no NDA)"; the reproducible
  precision/recall/timing above; "usable as historical weak supervision for salient events"; tooling exists
  and is tested.
- PROHIBITED: any live, point-in-time, predictive, or market-edge claim from commentary; any clean
  ground-truth claim for low-precision classes; any use in runtime/trading/Kalshi/paper-trading.
