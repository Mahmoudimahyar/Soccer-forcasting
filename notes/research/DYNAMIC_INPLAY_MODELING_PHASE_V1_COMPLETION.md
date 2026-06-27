# Dynamic In-Play Intelligence, Player-State, xG Fusion & Calibration Program V1 — COMPLETION

research_only · experimental · not_runtime_approved · not_trade_eligible · not_live_eligible ·
KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Run id `truth_20260626_134931` · worktree `worldcup-research-truth-fusion` · branch `research-truth-full-corpus-xg-fusion-v1`.
Controller: `deep_research_supervisor.py` with `configs/dynamic_inplay_modeling_phase_v1.yaml` (16-job queue, same run id,
resumed via `--resume-run-id`, offline by construction). All 16 jobs complete; api_used=0 (no external API).

## Datasets built (real, from the full local corpus)
- Dynamic causal panel: 2,818 fixtures with events+lineups (627 international, 2,191 club); 68,281 snapshot rows.
- International regulation W/D/L target table: **14,920 rows / 627 matches** (H 6,563 / A 4,882 / D 3,475), 100% reconciled-exact, 0 club rows, snapshot_minute ≤ 90.
- xG-enriched international table joined to the 4,386-row xG snapshot set (258 exact-bridge matches).
- Full temporal player priors (4 categories: exposure/recency, regularized shrunk contribution, team composition, substitution-delta) — coverage 90.4% of international decision snapshots.
- Dynamic xG state (cumulative/rolling/momentum/SoT/completeness, source-aware missingness). 45 deterministic integrity/leakage tests; full suite **324 passed, 20 skipped**.

## Evaluation (leakage-safe, preregistered)
Primary forward-chaining by tournament (WC→AFCON→Euro→AsianCup→Copa, 4 folds) + secondary LOCO (5 folds), training-only fitting/calibration, **match-level** paired bootstrap, pre-2026 international only (3,135 snapshots; **no completed 2026 WC data** in selection/fitting/calibration). Backend scikit-learn multinomial logistic / Poisson / hazard.

Pooled forward-chain RPS: R0 (static anchor) 0.2235 · R1 (time+score) 0.1550 · **R2 (remaining-time Poisson) 0.1523 — best reference**. Player candidates P1–P5 ≈ 0.149–0.152; xG-subset candidates X1 0.143 / X2 0.133 / X3 0.135 (different, easier 258-match population).

## Decision ledger (honest outcome — `data/reference/model_decision_ledger.{csv,json}`)
| status | models |
|---|---|
| reference_only | R0, R1, R2, X2 |
| rejected | P1, P2, P3, P4, P5, X1, X3 |
| research_candidate_for_future_shadow_review | **NONE** |

**No candidate clears the preregistered promotion bar.** Several candidates post a lower raw pooled RPS than R2 (e.g. P5 0.1489, X2 0.1327) but are honestly rejected/kept-reference because they fail the match-level bootstrap-CI rule and/or degrade draw-channel calibration and/or are not consistent across ≥4 folds. A correctness fix was applied during finalization: R1 had been mis-scored as a *candidate* against the trivial static anchor R0 and falsely flagged a shadow-review candidate; R0/R1/R2 are reference-tier baselines and are now `reference_only`, leaving zero promoted candidates.

This is a **valid negative result**, which the sprint's success definition explicitly accepts: the system delivered the canonical dynamic dataset, the temporal player-prior system, the xG event-state dataset joined to exact international snapshots, the preregistered W/D/L + next-goal + discipline + xG-fusion evaluations, match-level uncertainty + calibration + ablations + failure analysis, and a single decision ledger that states exactly which models are reference/rejected/none-promoted.

## Mandatory ablations (real) + failure analysis
W/D/L ladder R2→P1→P2→P3→P4→P5, xG ladder R2→X1→X2→X3, next-goal ladder N1→N2→N3→N4, club-prior vs none, high vs low player coverage, xG-complete vs incomplete, plus a complex-feature-worsens diagnostic — all computed with real deltas (`mj_job11_ablations.json`). Structured failure analysis (`mj_job13_failure_analysis.json`): overconfident matches, draw-state, late-game, red-card-state, post-substitution, sparse player-history, club→international transfer, xG-momentum, complex-feature-worsens cases.

## Hard completion gates (Phase 9) — all 20 objectively true
Datasets (1–3) exist; tests pass (4); primary W/D/L (5), LOCO (6), xG-subset (7) ran; next-goal (8) + discipline (9) ran; ablations (10), calibration+bootstrap (11), failure analysis (12) ran; decision ledger (13) exists with real metrics; no 2026 WC in selection (14); collector unchanged (15); no runtime/trading/Kalshi/paper/risk path changed (16); artifacts reproducible from manifests (17); raw gitignored (18); no secret exposed (19); conclusions follow the preregistration (20).

## Isolation / safety (unchanged)
Active collector `WorldCupShadowCollector` = main checkout `worldcup_draw_model_lab_FINAL` @ **dc73318**, clean, task Ready (never pointed at the research worktree). **B1, frozen M2, M1–M5, candidate.py, approved_models.yaml, trading, paper trading, Kalshi, risk, .env, and the active collector remain unchanged.** No model promoted to runtime. `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`. No external API/Odds/StatsBomb call in this phase.
