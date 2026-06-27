# Residual Goal-Intensity Dataset — Data Card (Phase 1)

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

## What this is

A leakage-safe **residual goal-intensity** plane built ON TOP OF the already-validated
international event-process snapshots. For each eligible in-play snapshot it attaches the **W2
reference** remaining home/away/total goal **intensities** and the W2 final H/D/A probabilities,
then defines the near-term competing-risk + remaining-goal **targets** and the **residuals**
(observed minus W2) plus causal **regime** labels that a later selective corrector
(`research.residual.selective_correction_r4`) will gate on.

W2 is a **reference intensity, not a competing classifier.** It is the parameter-free remaining-time
Poisson reference reimplemented in `wcdrawlab.research.dynamic_models`
(`r2_remaining_time_poisson`, `R2_BASE = 1.35` goals per team per 90'). The home and away reference
intensities are identical by construction (the reference has no team prior); the whole point of the
residual layer is to learn *when* the event-process state warrants nudging away from that symmetric
baseline.

## Provenance / lineage

| Layer | Source | Owner |
|---|---|---|
| Raw events | StatsBomb open-data event JSON (regulation only) | `statsbomb_raw` / `statsbomb_raw_prior` (read-only prior cache) |
| International population | exact `api<->statsbomb` bridge (258 exact intl rows) | `api_statsbomb_match_bridge_v1.csv` |
| Event-process snapshots | `scripts/build_event_process_snapshots.py` (reused, not reinvented) | `data/processed/event_process_snapshots/` |
| W2 reference | `dynamic_models.r2_remaining_time_poisson` / `R2_BASE` | reference intensity `research.intensity.w2_home_away_i0` |
| **This layer** | `scripts/build_residual_goal_intensity_dataset.py` | `data/processed/residual_goal_intensity/` |

Raw stays gitignored. The active collector checkout
(`C:/Users/Mahyar/worldcup_draw_model_lab_FINAL`) is never read — `data_roots` fails closed on it.
No network / API / Odds calls. **No completed-2026-World-Cup match participates** (corpus is
2018 / 2020 / 2022 / 2024 only).

## Real build (this worktree, current local data)

The full 7377-row prior build used a larger StatsBomb pull that is no longer on disk; only 60 prior
event JSONs remain locally, of which **58** map to exact international bridge rows. The dataset was
therefore **rebuilt from the 58 international matches actually present** — real data, honest counts:

| Quantity | Value |
|---|---|
| International residual rows (snapshots) | **7376** |
| International matches | **58** |
| Competitions (LOCO folds) | **5** — FIFA WC 2018, UEFA Euro 2020, FIFA WC 2022, Copa America 2024, UEFA Euro 2024 |
| Rows skipped (no regulation-final/WDL) | 0 |
| Join across the 3 tables | 1:1 on `(source_match_id, snapshot_minute)` |

## Output tables (`data/processed/residual_goal_intensity/`)

1. **`residual_goal_intensity_snapshots.csv`** — model INPUT plane: verbatim leakage-safe event-process
   state at the cutoff + W2 remaining home/away/total intensities + W2 final H/D/A + W2-implied
   near-term scoring/competing-risk probs (5/10/15m, right-censored) + completeness / xG-complete flags
   + pre-match anchor provenance + `source_sha256` / `engine_version`.
   Schema: `schemas/residual_goal_intensity_snapshot_v1.yaml`.
2. **`near_term_competing_risk_targets.csv`** — LABELS: (A) remaining home/away/total goals after the
   cutoff (regulation only); (B) competing-risk next 5/10/15m `{home_goal, away_goal, no_goal}`,
   right-censored at minute 90. Schema: `schemas/near_term_competing_risk_target_v1.yaml`.
3. **`selective_dynamic_correction.csv`** — RESIDUALS (observed − W2, both families) + causal regime
   labels + gate-support fields (`alpha_fallback_allowed`, `regime_cell`).
   Schema: `schemas/selective_dynamic_correction_v1.yaml`.

## Targets — horizon positive rates (real)

| Window | home_goal | away_goal | no_goal | right-censored |
|---|---|---|---|---|
| next 5m | 7.21% | 6.33% | 86.46% | 4.72% |
| next 10m | 12.26% | 10.63% | 77.12% | 10.53% |
| next 15m | 16.93% | 13.88% | 69.18% | 17.00% |

Remaining-goal targets (window-open rows, n=7375): mean remaining **total 1.107**, home 0.621,
away 0.486.

## Residual summary (observed − W2; real)

| Residual | mean | stdev | n |
|---|---|---|---|
| `resid_remaining_total` | **−0.186** | 1.012 | 7376 |
| `resid_remaining_home` | −0.025 | 0.759 | 7376 |
| `resid_remaining_away` | −0.160 | 0.742 | 7376 |
| `resid_any_goal_next5m` | −0.001 | 0.342 | 7376 |
| `resid_any_goal_next10m` | −0.018 | 0.418 | 7376 |
| `resid_any_goal_next15m` | −0.027 | 0.456 | 7376 |

**Honest reading:** the W2 reference (1.35 goals/team/90', symmetric) **slightly over-predicts**
remaining goals on this tournament-football corpus — most visibly for the *away* side
(`resid_remaining_away` ≈ −0.16) — i.e. these international fixtures are a touch lower-scoring than a
1.35-rate league prior and carry the usual home tilt the symmetric reference cannot express. That bias
is exactly the signal a selective corrector may exploit; Phase 1 only **measures** it (it fits
nothing). Near-term any-goal residuals are near zero on average, so most correction headroom is in the
remaining-goal / side-asymmetry channels, not the very-short windows.

## Causal regime labels

Computed from cutoff state ONLY (leakage-safe). 16 distinct `regime_time|regime_score|
regime_player_count` cells are populated; the modal cells are `early|level|even` (1749),
`mid|level|even` (1379), `late|one_goal|even` (1157). Player-up / two-goal regimes are sparse, as
expected. **Fixed-form, corpus-free thresholds** (documented here, never tuned to a test set):

- `regime_time`: early `t<30`, mid `30<=t<60`, late `t>=60`.
- `regime_score`: `|goals_diff|` → level / one_goal / two_plus; `regime_lead_side` from the sign.
- `regime_player_count`: from `players_diff` (sendoffs only; subs never change count).
- `regime_advantage`: sign of (score-lead sign + player-count sign).
- `regime_recent_pressure`: `high` if last-10m total xG ≥ 0.30 **or** ≥ 3 shots in last 10m.
- `regime_recent_transition`: `high` if recent recoveries+turnovers burst ≥ threshold.
- `regime_set_piece`: `recent` if a corner/attacking-FK has occurred and a shot fell in the last window.
- `regime_high_xg_chance`: `recent` if minutes-since-major-chance ≤ 5.
- `regime_completeness`: `sparse` if `<200` events by ≥60'; else `full` when xG present, else `partial`.
- `regime_xg_complete`: whether every shot in the match carried xG (`shot_xg` = `available_verified`).

## Leakage / isolation guarantees (enforced + tested)

- Every snapshot feature is taken **verbatim** from the leakage-safe event-process snapshot
  (events with regulation clock-minute ≤ t; period ∈ {1,2}; minute ≤ 90).
- The W2 reference is a closed form of `(score_diff, remaining)` **only** — no future information.
- Targets/residuals live in **separate tables** and are never input features (residuals embed labels).
- `remaining_*` goals = regulation-final − goals-at-cutoff; the final is a label, never fed back.
- Competing-risk windows are **right-censored** at the regulation boundary (`h_eff = min(h, 90−t)`).
- **Extra-time and shootout goals never count**; ET/shootout periods (≥3) are excluded upstream and
  re-verified here. Own goals are credited to the **benefiting** side (`"Own Goal For"`), and the
  conceding `"Own Goal Against"` is not double-counted.
- **Club rows are never emitted** (only `comp_type == 'international'`); club snapshots remain a
  separate auxiliary file and are never used as international test rows.
- Missing source fields are **flagged** (`xg_complete`, `source_quality_*`), never imputed as 0.
- `source_sha256` + `engine_version` are preserved on every row for traceability.

## Reproduce

```bash
# 1) materialise upstream event-process snapshots (reused, not reinvented)
python scripts/build_event_process_snapshots.py --run-id residual_phase1_build
# 2) build the residual goal-intensity plane
python scripts/build_residual_goal_intensity_dataset.py --run-id residual_phase1_build
# 3) audit every invariant on the produced files
python scripts/audit_residual_goal_intensity_dataset.py        # -> status: ok
# 4) tests (synthetic always-on + integration on the real dataset)
python -m pytest tests/test_residual_intensity_dataset.py -q   # -> 43 passed
```

The build is **deterministic** — a second run produces byte-identical CSVs
(`test_real_deterministic_rebuild_byte_identical`).

## Scope / non-goals (Phase 1)

This phase **builds the dataset + targets + residual/regime plane and tests it**. It fits no model,
selects no candidate, and tunes nothing. The selective corrector
(`research.residual.selective_correction_r4`) — which must allow `alpha=0` fallback to W2, choose
`alpha` in-train, and report correction coverage + corrected-vs-fallback performance — is a later
phase that consumes these three tables.

## Allowed downstream model classes (for the consuming phases, not used here)

ridge/elastic-net Poisson/neg-binomial, regularized discrete-time competing-risk hazard, multinomial
logistic, HistGradientBoosting (small predeclared grid only), isotonic/logistic calibration in-train,
fixed-form weighted blends, Monte-Carlo simulation from intensities. No neural/transformer/LLM,
broad architecture search, or test-set tuning.
