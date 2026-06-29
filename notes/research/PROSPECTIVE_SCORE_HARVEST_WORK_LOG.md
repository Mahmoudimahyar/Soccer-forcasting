# Prospective Score Harvest — Work Log

## 2026-06-29
- Recon: enumerated WorldCup scheduled tasks; recorded WorldCupShadowCollector isolation (main checkout,
  healthy, 5-min, 47/500 credits) and active WorldCupHierarchicalDomainTransferRun (own worktree) — not touched.
- Read scoring code (`scripts/live_2026_shadow.py`, `scripts/windows/shadow_collector_cycle.py`).
- **Root cause demonstrated:** `score()` requires `results_2026_footballdata.csv` status==FINISHED; that file
  is stale (FINISHED only through 06-20); all 35 predicted matches (06-24..06-28) are TIMED; the collector
  cycle never refreshes results (only fetches odds). Join → 0 scored rows; metrics written empty; rc=0.
  Verified: 680/680 predictions resolve a team-pair; 0/680 resolve a FINISHED outcome; 35/35 predicted
  matches present in results file but all status=TIMED.
- Created isolated worktree `prospective-score-harvest-v1` @ dc73318; wrote collector-isolation record + durable state files.
- Phase 0: forensic freeze — 680 preds, all valid, 35 fixtures, 100% pre-kickoff; input manifest + hashes.
- Phase 1: root-cause audit + 14-candidate failure matrix (primary = #12 result-source-never-refreshed).
- Phase 2: result reconciliation — football-data.org refresh returns 72/72 group FINISHED; 35/35 universe
  fixtures verified_final; canonical result records + schemas + audit (all_ok); no Odds API. + 14 recon tests.
- Phase 3: locked snapshot-selection preregistration; selection → 34 primary fixtures, 1 excluded. + 6 tests.
- Phase 4: independent idempotent harvester (append-only, score_key, integrity audit). + 13 tests. 33 new tests pass.
- Phase 5: backfill — 34/35 scored, 1 excluded (no_common_market_snapshot); idempotent (+0 on rerun).
- Phase 6: benchmark — Tier C (n=34); 0/24 paired deltas exclude zero; decision ledger (no promotion).
- Phase 7: deployment decision — retain independent harvester; defer collector patch; deploy/rollback scaffolds.
- Phase 8: durable harvester + watchdog installed, proven via real scheduled run (rc 0, terminal), then disabled.
- Phase 9: full worktree suite 208 passed/0 failed (excl. 2 files needing gitignored data, which pass in main);
  collector + hierarchical-transfer untouched/healthy. Completion report written. COMPLETE.
