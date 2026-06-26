# Dynamic Modeling — Current Truth (verified 2026-06-26)
research_only. Run id truth_20260626_134931; worktree worldcup-research-truth-fusion.
- API-Football player-history corpus: 2000/2000 raw-backed (events+lineups), canonical root self-contained (corpus_coverage.py rate=1.0).
- Reconciliation: data/reference/canonical_counts_ledger.json (960 reconciled, regulation_exact, sendings_off=128).
- Exact API<->StatsBomb bridge: 258 exact international matches (api_statsbomb_match_bridge_v1.csv, prior worktree).
- StatsBomb cache: 258/258 valid exact-bridge event files (statsbomb_cache_audit.json), all xG fields.
- xG snapshot join: 4386 audited xG-eligible regulation international snapshots (xg_snapshot_join_v1.csv, audit all-pass).
- Inherited infra reused: player_history.py, player_impact_models.py, _common.py (rps/logloss3/brier_draw/calibration/loco_folds/match_bootstrap_ci), inplay_dataset/replay, statsbomb_inplay, xg_features/xg_inplay.
- Prior player-impact result: PARTIAL (built on 3% corpus) -> must be RERUN on the complete corpus + real xG snapshots.
- Collector dc73318 clean, task Ready -> MAIN checkout (isolated). KALSHI=false TRADING=paper.
